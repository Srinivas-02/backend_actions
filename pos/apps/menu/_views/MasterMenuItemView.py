import base64
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework import status
from django.db import transaction
from pos.apps.menu.models import MasterMenuItem, MasterMenuCategory,LocationMenuItem
from pos.utils.logger import POSLogger

logger = POSLogger()

class MasterMenuItemView(APIView):
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def encode_image_to_data_url(self, raw_bytes):
        if not raw_bytes:
            return None
        base64_string = base64.b64encode(raw_bytes).decode('utf-8')
        return f"data:image/jpeg;base64,{base64_string}"

    def get(self, request, pk=None):

        if not (getattr(request.user, "is_super_admin", False) or getattr(request.user, "is_franchise_admin", False)):
            return Response({'error': 'not allowed'}, status=status.HTTP_403_FORBIDDEN)
        # List all or get a specific item by pk
        if pk:
            try:
                item = MasterMenuItem.objects.get(pk=pk)
                data = {
                    'id': item.id,
                    'name': item.name,
                    'description': item.description,
                    'price': float(item.price),
                    'category_id': item.category.id,
                    'category_name': item.category.name,
                    'image': self.encode_image_to_data_url(item.image),
                }
                return Response(data)
            except MasterMenuItem.DoesNotExist:
                return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        else:
            items = MasterMenuItem.objects.filter(is_active=True).select_related('category')
            data = [{
                'id': item.id,
                'name': item.name,
                'description': item.description,
                'price': float(item.price),
                'category_id': item.category.id,
                'category_name': item.category.name,
                'image': self.encode_image_to_data_url(item.image),
                'is_active': item.is_active
            } for item in items]
            return Response({'menu_items': data})

    def post(self, request):
        if not getattr(request.user, "is_super_admin", False):
            return Response({'error': 'only super admin is allowed'}, status=status.HTTP_403_FORBIDDEN)
        try:
            logger.info(f"\n\n\n POST /master-menu-items/ with data: {request.data} \n\n\n")
            name = request.data.get('name')
            price = request.data.get('price')
            description = request.data.get('description')
            category_id = request.data.get('category_id')
            
            # Check for duplicate names
            if MasterMenuItem.objects.filter(name__iexact=name, is_active=True).exists():
                return Response({'error': f'Menu item with name "{name}" already exists'}, status=status.HTTP_400_BAD_REQUEST)
            
            category = MasterMenuCategory.objects.get(pk=category_id)
            image_bytes = None
            uploaded_file = request.FILES.get('image')
            if uploaded_file:
                image_bytes = uploaded_file.read()
            new_item = MasterMenuItem.objects.create(
                name=name,
                price=price,
                description=description,
                category=category,
                image=image_bytes or None
            )
            data = {
                'id': new_item.id,
                'name': new_item.name,
                'description': new_item.description,
                'price': float(new_item.price),
                'category_id': new_item.category.id,
                'category_name': new_item.category.name,
                'image': self.encode_image_to_data_url(new_item.image)
            }
            return Response(data, status=status.HTTP_201_CREATED)
        except MasterMenuCategory.DoesNotExist:
            return Response({'error': 'Category not found'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.info(f"Exception in POST /master-menu-items/: {e}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, pk=None):
        if not getattr(request.user, "is_super_admin", False):
            return Response({'error': 'only super admin isallowed'}, status=status.HTTP_403_FORBIDDEN)
        if not pk:
            return Response({'error': 'ID required for update'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            item = MasterMenuItem.objects.get(pk=pk)
            
            # Check for duplicate names (excluding current item)
            if 'name' in request.data:
                name = request.data.get('name')
                if MasterMenuItem.objects.filter(name__iexact=name, is_active=True).exclude(pk=pk).exists():
                    return Response({'error': f'Menu item with name "{name}" already exists'}, status=status.HTTP_400_BAD_REQUEST)
                item.name = name
                
            if 'price' in request.data:
                item.price = request.data.get('price')
            if 'description' in request.data:
                item.description = request.data.get('description')
            if 'category' in request.data:
                cat_id = request.data.get('category')
                category = MasterMenuCategory.objects.get(pk=cat_id)
                item.category = category
            uploaded_file = request.FILES.get('image')
            if uploaded_file:
                image_bytes = uploaded_file.read()
                item.image = image_bytes
            item.save()
            data = {
                'id': item.id,
                'name': item.name,
                'description': item.description,
                'price': float(item.price),
                'category_id': item.category.id,
                'category_name': item.category.name,
                'image': self.encode_image_to_data_url(item.image)
            }
            return Response(data, status=status.HTTP_200_OK)
        except MasterMenuItem.DoesNotExist:
            return Response({'error': 'Menu item not found'}, status=status.HTTP_404_NOT_FOUND)
        except MasterMenuCategory.DoesNotExist:
            return Response({'error': 'Category not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.info(f"Exception in PUT /master-menu-items/: {e}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    

    def delete(self, request, pk=None):
        if not getattr(request.user, "is_super_admin", False):
            return Response({'error': 'only super admin is  allowed'}, status=status.HTTP_403_FORBIDDEN)
        if not pk:
            return Response({'error': 'ID required for delete'}, status=status.HTTP_400_BAD_REQUEST)
        
        item = get_object_or_404(MasterMenuItem, pk=pk)

        try:
            with transaction.atomic():

                item.is_active = False
                item.save(update_fields=["is_active"])

                # unassign and make this item unavailable for all locations
                updated = LocationMenuItem.objects.filter(menu_item=item).update(
                    is_assigned=False,
                    is_available=False,
                )

            return Response(
                {
                    'status': 'success',
                    'message': f"Menu item '{item.name}' soft deleted successfully",
                    'unassigned_locations': updated
                },
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
