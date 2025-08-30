from django.urls import path
from .views import OrderView, OrderReceiptView, OrderHistoryView

urlpatterns = [
   
    path('create-order/', OrderView.as_view()),
    path('generate-order-receipt/<int:order_id>/', OrderReceiptView.as_view()),
    path('history/', OrderHistoryView.as_view()),

]