from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from pos.apps.inventory.models import MasterIngredient
from pos.utils.logger import POSLogger

class IngredientsArchiveView(APIView):

    def get(self,request):
        if not getattr(request.user, "is_super_admin", False):
            return Response({'error': 'Only super admin can view archived items'}, status=403)

        archived_ingredients  = MasterIngredient.objects.filter(is_active=False)
        data = []
        for item in archived_ingredients:
            data.append({
                'id': item.id,
                'name': item.name,
                'unit': item.unit,
                'reorder_threshold': float(item.reorder_threshold),
                'shelf_life': str(item.shelf_life) if item.shelf_life else None,
                'is_composite': item.is_composite,
                'recipe_yield': float(item.recipe_yield) if item.recipe_yield else None,
                'recipe_ratios': item.recipe_ratios,
                'is_active': item.is_active,
            })
        return Response({
            "status": "success",
            "message": "Archived ingredients retrieved successfully",
            "data": data,
            "status_code": 200
        })
    
class RestoreIngredientView(APIView):

    def post(self, request, ingredient_id):
        if not getattr(request.user, "is_super_admin", False):
            return Response({'error': 'Only super admin can restore items'}, status=403)

        try:
            ingredient = MasterIngredient.objects.get(id=ingredient_id, is_active=False)
            ingredient.is_active = True
            ingredient.save(update_fields=["is_active"])

            return Response({
                "status": "success",
                "message": f"Ingredient '{ingredient.name}' restored successfully",
                "status_code": 200
            }, status=status.HTTP_200_OK)

        except MasterIngredient.DoesNotExist:
            return Response({
                "status": "error",
                "message": "Archived ingredient not found",
                "status_code": 404
            }, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            POSLogger.error(f"Error restoring ingredient {ingredient_id}: {e}")
            return Response({
                "status": "error",
                "message": "Failed to restore ingredient",
                "status_code": 500
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)