from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from pos.apps.orders.models import Order, OrderItem
from pos.apps.menu.models import MenuItemModel
from pos.apps.locations.models import LocationModel
import random

class OrderReceiptView(APIView):
    def get(self, request, order_id):
        try:
            order = Order.objects.get(id=order_id)
            items = OrderItem.objects.filter(order=order)
        except Order.DoesNotExist:
            return Response(
                {"error": "Order not found"}, 
                status=status.HTTP_404_NOT_FOUND
            )

        # Build receipt content
        receipt_content = [
            f"Order Number: {order.order_number}",
            f"Date: {order.order_date.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Location: {order.location.name}",
            f"Customer: {order.customer_name or 'Walk-in'}",
            f"Table: {order.table_number or 'N/A'}",
            "----------------------------------------"
        ]

        for item in items:
            receipt_content.extend([
                f"{item.menu_item.name} x {item.quantity}",
                f"Price per unit: {item.price}",
                f"Notes: {item.notes or 'None'}",
                "----------------------------------------"
            ])

        receipt_content.append(f"TOTAL AMOUNT: {order.total_amount}")
        receipt_content.append("\nThank you for your order!")

        # Format for thermal printer
        receipt_text = "\n".join(receipt_content)
        
        return Response({
            'receipt': receipt_text,
            'order_number': order.order_number
        }, status=status.HTTP_200_OK)