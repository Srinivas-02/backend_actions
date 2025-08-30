from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
import datetime
from django.db.models import Q
from pos.apps.orders.models import Order, OrderItem
from django.shortcuts import get_object_or_404
from pos.utils.logger import POSLogger

logger = POSLogger(__name__)

class OrderHistoryView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """
        Get order history with various filters
        Params:
            - location_id: Filter by location
            - date_from: Filter by date range (YYYY-MM-DD)
            - date_to: Filter by date range (YYYY-MM-DD)
            - order_id: Get specific order details
        """
        user = request.user
        order_id = request.query_params.get('order_id')
        
        # If order_id is provided, return detailed information about that order
        if order_id:
            try:
                # Apply permissions based on user role
                if hasattr(user, 'is_super_admin') and user.is_super_admin:
                    order = get_object_or_404(Order, id=order_id)
                elif hasattr(user, 'is_franchise_admin') and (user.is_franchise_admin or user.is_staff_member):
                    user_locations = user.locations.all()
                    order = get_object_or_404(Order, id=order_id, location__in=user_locations)
                else:
                    logger.warning(f"Unauthorized order access attempt for order {order_id} by {user.email}")
                    return Response({"error": "Not authorized to access this order"}, status=status.HTTP_403_FORBIDDEN)
                
                # Get order items
                order_items = order.items.all().values(
                     'menu_item_id', 'menu_item__menu_item__name', 'quantity', 'price', 'menu_item__menu_item__category__name'
                )
                
                # Add menu item name if available
                for item in order_items:
                    menu_item = order.items.get(id=item['id']).menu_item
                    item['menu_item__menu_item__name'] = menu_item.name if menu_item else None
                    item['order_id'] = order.id
                
                response_data = {
                    'order_id': order.id,
                    'placed_at': order.placed_at,
                    'total_amount': str(order.total_amount),  # Convert Decimal to string
                    'is_cancelled': order.is_cancelled,
                    'updated_at': order.updated_at,
                    'cancelled_at': order.cancelled_at,
                    'location': {
                        'id': order.location.id,
                        'name': order.location.name
                    },
                    'payment_mode': order.payment_mode,
                    'order_items': list(order_items),
                    'token_number': order.token_number,
                }
                
                # Add processor information if available
                if order.processed_by:
                    response_data['processed_by'] = {
                        'id': order.processed_by.id,
                        'name': f"{order.processed_by.first_name} {order.processed_by.last_name}".strip()
                    }
                
                logger.info(f"Order {order_id} details retrieved by {user.email}")
                return Response(response_data)
            except Exception as e:
                logger.error(f"Error retrieving order {order_id} for {user.email}: {str(e)}")
                return Response({"error": str(e)}, status=status.HTTP_404_NOT_FOUND)
        
        # Otherwise, return filtered list of orders
        try:
            # Apply filters
            location_id = request.query_params.get('location_id')
            date_from = request.query_params.get('date_from')
            date_to = request.query_params.get('date_to')
            
            # Base queryset with role-based filtering
            if hasattr(user, 'is_super_admin') and user.is_super_admin:
                orders = Order.objects.all()
            elif hasattr(user, 'is_franchise_admin') and (user.is_franchise_admin or user.is_staff_member):
                user_locations = user.locations.all()
                orders = Order.objects.filter(location__in=user_locations)
            else:
                logger.warning(f"Unauthorized order history access attempt by {user.email}")
                return Response({"error": "Not authorized to view order history"}, status=status.HTTP_403_FORBIDDEN)
            
            # Apply additional filters
            if location_id:
                if not (hasattr(user, 'is_super_admin') and user.is_super_admin) and \
                   not (hasattr(user, 'locations') and user.locations.filter(id=location_id).exists()):
                    logger.warning(f"Unauthorized location access attempt for location {location_id} by {user.email}")
                    return Response({"error": "You don't have access to this location"}, 
                                   status=status.HTTP_403_FORBIDDEN)
                orders = orders.filter(location_id=location_id)
            
            # Date range filtering
            if date_from:
                # date_from is like '2025-08-12'
                local_from = datetime.datetime.strptime(date_from, "%Y-%m-%d")
                local_from = timezone.make_aware(local_from, timezone.get_current_timezone())  # e.g. IST
                utc_from = local_from.astimezone(datetime.timezone.utc)
                orders = orders.filter(placed_at__gte=utc_from)

            if date_to:
                local_to = datetime.datetime.strptime(date_to, "%Y-%m-%d")
                local_to = datetime.datetime.combine(local_to, datetime.time.min) + datetime.timedelta(days=1) - datetime.timedelta(seconds=1)
                local_to = timezone.make_aware(local_to, timezone.get_current_timezone())
                utc_to = local_to.astimezone(datetime.timezone.utc)
                orders = orders.filter(placed_at__lte=utc_to)

            # Order by date, newest first
            orders = orders.order_by('-placed_at')
            
            # Serialize the data
            response_data = []
            for order in orders:
                order_items_raw = order.items.all().values(
                     'menu_item_id', 'menu_item__menu_item__name', 'quantity', 'price', 'menu_item__menu_item__category__name'
                )
                order_items = []
                for item in order_items_raw:
                    order_items.append({
                        'menu_item_id': item['menu_item_id'],
                        'menu_item_name': item['menu_item__menu_item__name'],  # renamed
                        'menu_category': item['menu_item__menu_item__category__name'],  # renamed
                        'quantity': item['quantity'],
                        'price': item['price'],
                    })
                order_data = {
                    'order_id': order.id,
                    'total_amount': order.total_amount,
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
                    'order_items': list(order_items),
                    'token_number': order.token_number,
                }
                response_data.append(order_data)
            
            logger.info(f"Order history retrieved by {user.email}")
            return Response(response_data)
            
        except Exception as e:
            logger.error(f"Error retrieving order history for {user.email}: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)