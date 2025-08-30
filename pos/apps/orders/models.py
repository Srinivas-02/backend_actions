from django.db import models
from pos.apps.locations.models import LocationModel
from pos.apps.menu.models import LocationMenuItem
from pos.apps.accounts.models import User
from django.utils import timezone

class Order(models.Model):
    id = models.AutoField(primary_key=True)  # backend unique ID
    location = models.ForeignKey(LocationModel, on_delete=models.CASCADE)
    placed_at = models.DateTimeField() #will send from frontend for offline mode
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='processed_orders')
    is_cancelled = models.BooleanField(default=False)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    payment_mode = models.CharField(max_length=50, default='cash')
    token_number = models.PositiveIntegerField()
    token_date = models.DateField(default=timezone.localdate)

    class Meta:
        unique_together = ('location', 'token_date', 'token_number')  # ensure uniqueness

    def save(self, *args, **kwargs):
        if not self.token_number:
            local_date = timezone.localtime(self.placed_at).date()
            last_token = Order.objects.filter(location=self.location, token_date=local_date).order_by('-token_number').first()
            self.token_number = (last_token.token_number + 1) if last_token else 1
            self.token_date = local_date
        super().save(*args, **kwargs)

    def __str__(self):
        status = "Cancelled" if self.is_cancelled else "Active"
        return f"Token #{self.token_number} ({status}) at {self.location.name}"

class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    menu_item = models.ForeignKey(LocationMenuItem, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.quantity}x {self.menu_item.name} for Order #{self.order.id}"