from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from pos.apps.orders.models import Order, OrderItem
from pos.apps.menu.models import LocationMenuItem
from pos.apps.locations.models import LocationModel
from pos.apps.accounts.models import User
from pos.utils.logger import POSLogger

logger = POSLogger(__name__)

class OrderView(APIView):
    def post(self, request):
        """Create a new order"""
        # Extract basic order data
        data = request.data
        location_id = data.get('location_id')
        items = data.get('items', [])
        payment_mode = data.get('payment_mode', 'cash')
        placed_at_str = data.get('placed_at')
        if placed_at_str:
            dt = parse_datetime(placed_at_str)  # parse to datetime
            if timezone.is_naive(dt):
                dt = timezone.make_aware(dt, timezone.utc)  # force UTC awareness
            placed_at = dt
        else:
            logger.info(f"\n\n\n\n\n the placed at is not parsed \n\n\n")
            placed_at = timezone.now()
        # Validate authentication   
        if not request.user.is_authenticated:
            logger.warning("Unauthorized order creation attempt by anonymous user")
            return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)

        # Validate location
        try:
            location = LocationModel.objects.get(id=location_id)
        except LocationModel.DoesNotExist:
            logger.warning(f"Attempt to create order with invalid location ID {location_id} by {request.user.email}")
            return Response({"error": "Invalid location ID"}, status=status.HTTP_400_BAD_REQUEST)

        # Check location access for franchise admin
        if request.user.is_franchise_admin:
            admin = get_object_or_404(User, id=request.user.id, is_franchise_admin=True)
            if location_id not in [loc['id'] for loc in list(admin.locations.values('id'))]:
                logger.warning(f"Franchise admin {request.user.email} attempted to create order in unauthorized location {location_id}")
                return Response({"error": "You do not have access to this location"}, status=status.HTTP_403_FORBIDDEN)

        # Validate items
        if not items:
            logger.warning(f"Order creation attempt with no items by {request.user.email}")
            return Response({"error": "No items in order"}, status=status.HTTP_400_BAD_REQUEST)

        total_amount = 0
        order_items = []

        # Process each item
        for item in items:
            menu_item_id = item.get('menu_item_id')
            quantity = item.get('quantity', 1)

            try:
                menu_item = LocationMenuItem.objects.get(id=menu_item_id)
                # Ensure menu item belongs to the location
                if menu_item.location.id != location_id:
                    logger.warning(f"Menu item {menu_item_id} does not belong to location {location_id} in order by {request.user.email}")
                    return Response(
                        {"error": f"Menu item {menu_item_id} does not belong to location {location_id}"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except LocationMenuItem.DoesNotExist:
                logger.warning(f"Attempt to add invalid menu item ID {menu_item_id} to order by {request.user.email}")
                return Response(
                    {"error": f"Invalid menu item ID: {menu_item_id}"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Validate quantity
            if not isinstance(quantity, int) or quantity < 1:
                logger.warning(f"Invalid quantity {quantity} for menu item {menu_item_id} by {request.user.email}")
                return Response(
                    {"error": f"Invalid quantity for menu item {menu_item_id}"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Calculate item total
            item_price = menu_item.price
            total_amount += item_price * quantity

            # Store item details
            order_items.append({
                'menu_item': menu_item,
                'quantity': quantity,
                'price': item_price
            })

        # Create order
        try:
            order = Order(
                location=location,
                total_amount=total_amount,
                processed_by=request.user,
                placed_at=placed_at or timezone.now(),
                is_cancelled=False,
                payment_mode=payment_mode,
            )
            order.save()
            # Create order items
            for item in order_items:
                OrderItem.objects.create(
                    order=order,
                    menu_item=item['menu_item'],
                    quantity=item['quantity'],
                    price=item['price']
                )
            logger.info(f"Order {order.id} created by {request.user.email} with total {total_amount}")
        except Exception as e:
            logger.error(f"Error creating order for {request.user.email}: {str(e)}")
            return Response(
                {"error": str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response({
            'order_id': order.id,
            'total_amount': str(order.total_amount),
            'order_items': list(order.items.values('menu_item_id', 'menu_item__menu_item__name', 'quantity', 'price')),
            'placed_at': order.placed_at,
            'is_cancelled': order.is_cancelled,
            'updated_at': order.updated_at,
            'location': {
                        'id': order.location.id,
                        'name': order.location.name
                    },
            'cancelled_at': order.cancelled_at,
            'payment_mode': order.payment_mode,
            'token_number': order.token_number,
        }, status=status.HTTP_201_CREATED)

    def put(self, request):
        """Update an existing order"""
        # Extract order ID and data
        order_id = request.data.get('order_id')
        location_id = request.data.get('location_id')
        items = request.data.get('order_items', [])
        payment_mode = request.data.get('payment_mode', 'cash')
        # Validate authentication
        if not request.user.is_authenticated:
            logger.warning("Unauthorized order update attempt by anonymous user")
            return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)

        # Validate order ID
        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            logger.warning(f"Attempt to update non-existent order {order_id} by {request.user.email}")
            return Response({"error": "Order not found"}, status=status.HTTP_404_NOT_FOUND)

        # Check if order is cancelled
        if order.is_cancelled:
            logger.warning(f"Attempt to update cancelled order {order_id} by {request.user.email}")
            return Response({"error": "Cannot update a cancelled order"}, status=status.HTTP_400_BAD_REQUEST)

        # Check location access for franchise admin
        if request.user.is_franchise_admin:
            admin = get_object_or_404(User, id=request.user.id, is_franchise_admin=True)
            if order.location.id not in [loc['id'] for loc in list(admin.locations.values('id'))]:
                logger.warning(f"Franchise admin {request.user.email} attempted to update order {order_id} in unauthorized location {order.location.id}")
                return Response({"error": "You do not have access to this order’s location"}, status=status.HTTP_403_FORBIDDEN)

        # Validate location if provided
        if location_id:
            try:
                location = LocationModel.objects.get(id=location_id)
                # Check location access for franchise admin
                if request.user.is_franchise_admin:
                    if location_id not in [loc['id'] for loc in list(admin.locations.values('id'))]:
                        logger.warning(f"Franchise admin {request.user.email} attempted to update order {order_id} to unauthorized location {location_id}")
                        return Response({"error": "You do not have access to this location"}, status=status.HTTP_403_FORBIDDEN)
            except LocationModel.DoesNotExist:
                logger.warning(f"Attempt to update order {order_id} with invalid location ID {location_id} by {request.user.email}")
                return Response({"error": "Invalid location ID"}, status=status.HTTP_400_BAD_REQUEST)
        else:
            location = order.location

        # Validate items
        if not items:
            logger.warning(f"Order update attempt with no items for order {order_id} by {request.user.email}")
            return Response({"error": "No items in order"}, status=status.HTTP_400_BAD_REQUEST)

        total_amount = 0
        order_items = []

        # Process each item
        for item in items:
            menu_item_id = item.get('menu_item_id')
            quantity = item.get('quantity', 1)

            try:
                menu_item = LocationMenuItem.objects.get(id=menu_item_id)
                # Ensure menu item belongs to the location
                if menu_item.location.id != location.id:
                    logger.warning(f"Menu item {menu_item_id} does not belong to location {location.id} in order update by {request.user.email}")
                    return Response(
                        {"error": f"Menu item {menu_item_id} does not belong to location {location.id}"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            except LocationMenuItem.DoesNotExist:
                logger.warning(f"Attempt to add invalid menu item ID {menu_item_id} to order {order_id} by {request.user.email}")
                return Response(
                    {"error": f"Invalid menu item ID: {menu_item_id}"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Validate quantity
            if not isinstance(quantity, int) or quantity < 1:
                logger.warning(f"Invalid quantity {quantity} for menu item {menu_item_id} in order {order_id} by {request.user.email}")
                return Response(
                    {"error": f"Invalid quantity for menu item {menu_item_id}"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Calculate item total
            item_price = menu_item.price
            total_amount += item_price * quantity

            # Store item details
            order_items.append({
                'menu_item': menu_item,
                'quantity': quantity,
                'price': item_price
            })

        # Update order
        try:
            # Update order fields
            order.location = location
            order.total_amount = total_amount
            order.processed_by = request.user
            order.payment_mode = payment_mode
            order.save()  # updated_at is automatically set by the model

            # Delete existing order items
            order.items.all().delete()

            # Create new order items
            for item in order_items:
                OrderItem.objects.create(
                    order=order,
                    menu_item=item['menu_item'],
                    quantity=item['quantity'],
                    price=item['price']
                )
            logger.info(f"Order {order.id} updated by {request.user.email} with total {total_amount}")
        except Exception as e:
            logger.error(f"Error updating order {order_id} for {request.user.email}: {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response({
            'order_id': order.id,
            'total_amount': str(order.total_amount),
            'placed_at': order.placed_at,
            'is_cancelled': order.is_cancelled,
            'updated_at': order.updated_at,
            'cancelled_at': order.cancelled_at,
            'processed_by': order.processed_by.email if order.processed_by else None,
            'location': {
                        'id': order.location.id,
                        'name': order.location.name
                    },
            'payment_mode': order.payment_mode,
            'order_items': list(order.items.values('menu_item_id', 'menu_item__menu_item__name', 'quantity', 'price', 'menu_item__menu_item__category__name')),
            'token_number': order.token_number
        }, status=status.HTTP_200_OK)

    def delete(self, request):
        """Cancel an order (soft deletion)"""
        # Extract order ID
        order_id = request.data.get('order_id')

        # Validate authentication
        if not request.user.is_authenticated:
            logger.warning("Unauthorized order cancellation attempt by anonymous user")
            return Response({"error": "Authentication required"}, status=status.HTTP_401_UNAUTHORIZED)

        # Validate order ID
        if not order_id:
            logger.warning(f"Order cancellation attempt without order ID by {request.user.email}")
            return Response({"error": "Order ID required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            logger.warning(f"Attempt to cancel non-existent order {order_id} by {request.user.email}")
            return Response({"error": "Order not found"}, status=status.HTTP_404_NOT_FOUND)

        # Check if already cancelled
        if order.is_cancelled:
            logger.warning(f"Attempt to cancel already cancelled order {order_id} by {request.user.email}")
            return Response({"error": "Order is already cancelled"}, status=status.HTTP_400_BAD_REQUEST)

        # Check location access for franchise admin
        if request.user.is_franchise_admin:
            admin = get_object_or_404(User, id=request.user.id, is_franchise_admin=True)
            if order.location.id not in [loc['id'] for loc in list(admin.locations.values('id'))]:
                logger.warning(f"Franchise admin {request.user.email} attempted to cancel order {order_id} from unauthorized location {order.location.id}")
                return Response({"error": "You do not have access to this order’s location"}, status=status.HTTP_403_FORBIDDEN)

        try:
            order.is_cancelled = True
            order.cancelled_at = timezone.now()
            order.save()
            logger.info(f"Order {order_id} cancelled by {request.user.email}")
            return Response({
                "order_id": order.id,
                "is_cancelled": order.is_cancelled,
                "cancelled_at": order.cancelled_at
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error cancelling order {order_id} for {request.user.email}: {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )