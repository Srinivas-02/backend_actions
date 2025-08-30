import base64
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser,JSONParser
from rest_framework.response import Response
from rest_framework import status
from pos.apps.accounts.models import User
from pos.apps.menu.models import MenuItemModel, CategoryModel
from pos.apps.locations.models import LocationModel
from pos.utils.logger import POSLogger

logger = POSLogger()
class MenuItemsView(APIView):

    # Include JSONParser so DELETE (and PATCH/PUT) can handle application/json
    parser_classes = (MultiPartParser, FormParser,JSONParser)


    def encode_image_to_data_url(self,raw_bytes):
            if not raw_bytes:
                return None
            base64_string = base64.b64encode(raw_bytes).decode('utf-8')
            return f"data:image/jpeg;base64,{base64_string}"

    def get(self, request):
        """Get all menu items or specific item if ID provided"""
        
        logger.info(f"request.user: {request.user.is_super_admin}, {request.user.is_franchise_admin}, {request.user.is_staff_member}")
        # Check if user is super admin or franchise admin
        # If not, return forbidden response
        if not request.user.is_super_admin and not request.user.is_franchise_admin:
            return Response({'error': 'not allowed'}, status=status.HTTP_403_FORBIDDEN)
        item_id = request.data.get('id')
        location_id = request.query_params.get('location_id')
        

        if item_id:
            try:
                item = MenuItemModel.objects.get(pk=item_id, is_available=True)
                if request.user.is_super_admin:
                    data = {
                        'id': item.id,
                        'name': item.name,
                        'description': item.description,
                        'price': float(item.price),
                        'category': item.category.name,
                        'location': item.location.id,
                        'image': self.encode_image_to_data_url(item.image)
                    }
                    return Response(data)
                elif request.user.is_franchise_admin:
                    admin = get_object_or_404(User, id=request.user.id, is_franchise_admin=True)
                    if item.location.id not in [loc['id'] for loc in list(admin.locations.values('id', 'name'))]:
                        return Response({'error': 'not allowed'})
                    data = {
                        'id': item.id,
                        'name': item.name,
                        'description': item.description,
                        'price': float(item.price),
                        'category': item.category.name,
                        'location': item.location.id,
                        'image': self.encode_image_to_data_url(item.image)
                    }
                    return Response(data)
                else:
                    return Response({'error': 'not allowed'})
            except MenuItemModel.DoesNotExist:
                return Response(
                    {'status': 'error', 'message': 'Menu item not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

        if location_id: 
            menu_itmes = MenuItemModel.objects.filter(
                is_available=True,
                location__id=location_id
            )
            logger.info(f"\n\n Menu items for location {location_id}: {menu_itmes}")
            

            if not menu_itmes.exists():
                return Response(
                    {'status': 'error', 'message': 'No menu items found for this location'},
                    status=status.HTTP_404_NOT_FOUND
                )
            data = [{
                'id': item.id,
                'name': item.name,
                'description': item.description,
                'price': float(item.price),
                'category': item.category.name,
                'location_id': item.location.id,
                'image': self.encode_image_to_data_url(item.image) if item.image else None
            } for item in menu_itmes]
            return Response({'menu_items': data})
           

        if request.user.is_super_admin:
            items = MenuItemModel.objects.filter(is_available=True)
        elif request.user.is_franchise_admin or request.user.is_staff_member:
            requester = get_object_or_404(User, id=request.user.id)
            items = MenuItemModel.objects.filter(
                is_available=True,
                location__in=requester.locations.all()
            )
        else:
            return Response({'error': 'not allowed'})

        data = [{
            'id': item.id,
            'name': item.name,
            'description': item.description,
            'price': float(item.price),
            'category': item.category.name,
            'location_id': item.location.id,
            'image': self.encode_image_to_data_url(item.image)
        } for item in items]
        return Response({'menu_items': data})

    def post(self, request):
        """Create new menu item"""
        try:
            if not (request.user.is_super_admin or request.user.is_franchise_admin):
                return Response({'error': 'not allowed'})
            

            name = request.data.get('name')
            price = request.data.get('price')
            descritption = request.data.get('description')
            category = CategoryModel.objects.get(id=request.data.get('category_id'))
            requested_loc_id = request.data.get('location_id')
            

            if str(category.location.id) != requested_loc_id:
                return Response({'error': 'category does not belong this location'})
                
            location = LocationModel.objects.get(id=requested_loc_id)
            
            # Check location access for franchise admin
            if request.user.is_franchise_admin:
                if not request.user.has_location_access(requested_loc_id):
                    return Response({'error': 'does not have access to this location'})
            
            image_bytes = None
            uploaded_file = request.FILES.get('image')
            if uploaded_file:
                 image_bytes = uploaded_file.read()

            # Create menu item
            new_item = MenuItemModel.objects.create(
                name=name,
                price=price,
                description=descritption,
                category=category,
                location=location,
                image=image_bytes or None,
                is_available=True
            )
            
            return Response({
                'status': 'success',
                'id': new_item.id,
                'name': new_item.name,
                'description': new_item.description,
                'price': float(new_item.price),
                'category': new_item.category.name,
                'location_id' : new_item.location.id,
                'image': self.encode_image_to_data_url(new_item.image)
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response(
                {'status': 'error', 'message': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    def put(self, request):
        """Update menu item (all fields), including replacing the image if provided"""
        try:
            item = MenuItemModel.objects.get(pk=request.data.get('id'))


            # 1) Update name
            if 'name' in request.data:
                item.name = request.data.get('name')

            # 2) Update price
            if 'price' in request.data:
                item.price = request.data.get('price')

            # 3) Update category (and validate its location)
            if 'category_id' in request.data:
                new_cat = CategoryModel.objects.get(id=request.data.get('category_id'))
                # If the new category doesn't belong to the same location, reject
                if new_cat.location.id != item.location.id:
                    return Response(
                        {'error': 'category does not belong to this location'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                item.category = new_cat

            # 4) Update location (and validate that category still matches, if category already set)
            if 'location_id' in request.data:
                new_loc = LocationModel.objects.get(id=request.data.get('location_id'))
                item.location = new_loc

                # If a category_id was not explicitly provided this round,
                # make sure the existing category still belongs to the new location:
                if item.category.location.id != new_loc.id:
                    return Response(
                        {'error': 'existing category does not belong to new location'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            # 5) Check for a new image file in request.FILES
            uploaded_file = request.FILES.get('image')
            if uploaded_file:
                logger.info(
                    f"PUT: updating image: name={uploaded_file.name}, "
                    f"size={uploaded_file.size}, content_type={uploaded_file.content_type}"
                )
                image_bytes = uploaded_file.read()
                item.image = image_bytes  # or `None` if you want to allow blank

            # 6) Save all changes
            item.save()

            return Response({'status': 'success'}, status=status.HTTP_200_OK)

        except MenuItemModel.DoesNotExist:
            return Response(
                {'status': 'error', 'message': 'Menu item not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except CategoryModel.DoesNotExist:
            return Response(
                {'status': 'error', 'message': 'Category not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except LocationModel.DoesNotExist:
            return Response(
                {'status': 'error', 'message': 'Location not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.info(f"Exception in PUT /menu/menu-items/: {e}")
            return Response(
                {'status': 'error', 'message': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


    def patch(self, request, item_id=None):
        """Partially update a menu item; if an image is included, replace it"""
        try:
            # Determine which ID to update
            item_id = item_id or request.data.get('id')
            if not item_id:
                return Response(
                    {'status': 'error', 'message': 'ID is required for update'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            item = MenuItemModel.objects.get(pk=item_id)

            # 1) Permissions (franchise_admin only for their own location, super_admin always OK)
            if request.user.is_franchise_admin:
                admin = get_object_or_404(User, id=request.user.id, is_franchise_admin=True)
                if item.location.id not in [loc['id'] for loc in admin.locations.values('id', 'name')]:
                    return Response({'error': 'not allowed'}, status=status.HTTP_403_FORBIDDEN)
            elif not request.user.is_super_admin:
                return Response({'error': 'not allowed'}, status=status.HTTP_403_FORBIDDEN)

            # 2) Update name if provided
            if 'name' in request.data:
                item.name = request.data.get('name')

            # 3) Update price if provided
            if 'price' in request.data:
                item.price = request.data.get('price')

            # update description if provided
            if 'description' in request.data:
                item.description = request.data.get('description')


            # 5) Update category (and verify it belongs to this location)
            if 'category_id' in request.data:
                new_cat = CategoryModel.objects.get(id=request.data.get('category_id'))
                if new_cat.location.id != item.location.id:
                    return Response(
                        {'error': 'category does not belong to this location'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                item.category = new_cat

            if 'location_id' in request.data:
                new_loc = LocationModel.objects.get(id=request.data.get('location_id'))
                item.location = new_loc

                # If a category_id was not explicitly provided this round,
                # make sure the existing category still belongs to the new location:
                if item.category.location.id != new_loc.id:
                    return Response(
                        {'error': 'existing category does not belong to new location'},
                        status=status.HTTP_400_BAD_REQUEST
                    )


            # 6) Check for a new image file in request.FILES
            uploaded_file = request.FILES.get('image')
            if uploaded_file:
                logger.info(
                    f"PATCH: updating image: name={uploaded_file.name}, "
                    f"size={uploaded_file.size}, content_type={uploaded_file.content_type}"
                )
                image_bytes = uploaded_file.read()
                item.image = image_bytes  # or `None` if you want to allow clearing it

            # 7) Save changes
            item.save()

            return Response({
                'status': 'success',
                'id': item.id,
                'name': item.name,
                'description': item.description,
                'price': float(item.price),
                'category': item.category.name,
                'location_id' : item.location.id,
                'image': self.encode_image_to_data_url(item.image)
            }, status=status.HTTP_201_CREATED)

        except MenuItemModel.DoesNotExist:
            return Response(
                {'status': 'error', 'message': 'Menu item not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except CategoryModel.DoesNotExist:
            return Response(
                {'status': 'error', 'message': 'Category not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.info(f"Exception in PATCH /menu/menu-items/: {e}")
            return Response(
                {'status': 'error', 'message': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

        

    def delete(self, request):
        """delete menu item"""
        try:
            item = MenuItemModel.objects.get(pk=request.data.get('id'))
            item.delete()
            return Response({'status': 'success'})
        
        except Exception as e:
            return Response(
                {'status': 'error', 'message': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )