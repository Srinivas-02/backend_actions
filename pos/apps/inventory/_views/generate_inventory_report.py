from datetime import datetime
from django.db import transaction
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from pos.apps.inventory.models import DailyInventory, LocationModel, LocationIngredient
from django.utils.timezone import localtime
from django.utils import timezone


def ensure_daily_rows(location, report_date):
    """
    Ensure DailyInventory rows exist for ALL currently assigned+available
    ingredients at (location, report_date). Creates only the missing ones.
    Returns the number of rows created.
    """
    # Assigned + available today + active master ingredient
    assigned_qs = (LocationIngredient.objects
                   .select_related('master_ingredient')
                   .filter(location=location, is_assigned=True, is_available=True, master_ingredient__is_active=True))

    # Already present in today's report
    existing_ids = set(DailyInventory.objects
                       .filter(location=location, date=report_date, location_ingredient__isnull=False)
                       .values_list('location_ingredient_id', flat=True))

    # Missing location_ingredients that need rows
    missing_lis = [li for li in assigned_qs if li.id not in existing_ids]
    if not missing_lis:
        return 0

    # Previous closing for each missing LocationIngredient 
    prev_rows = (DailyInventory.objects
                 .filter(location=location, date__lt=report_date, location_ingredient__in=missing_lis)
                 .order_by('location_ingredient', '-date')
                 .distinct('location_ingredient')  # Postgres only
                 .values('location_ingredient', 'closing_stock'))
    prev_map = {r['location_ingredient']: r['closing_stock'] for r in prev_rows}

    new_entries = []
    for li in missing_lis:
        opening = prev_map.get(li.id, 0.0)
        new_entries.append(DailyInventory(
            date=report_date,
            location_ingredient=li,
            location=location,
            opening_stock=opening,
            prepared_qty=0.0,
            used_qty=0.0,
            closing_stock=opening,
            raw_equiv=None,
        ))

    with transaction.atomic():
        DailyInventory.objects.bulk_create(new_entries, ignore_conflicts=True)

    return len(new_entries)


@api_view(['POST'])
def generate_inventory_report(request):
    """ Generates or refreshes a daily inventory report for a specific date and location. """

    report_date_str = request.data.get('date')
    location_id = request.data.get('location_id')

    if not report_date_str or not location_id:
        return Response(
            {'status': 'error', 'message': 'Date and location_id are required.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        report_date = datetime.strptime(report_date_str, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return Response(
            {'status': 'error', 'message': 'Invalid date format. Use YYYY-MM-DD.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if report_date > localtime(timezone.now()).date():
        return Response(
            {'status': 'error', 'message': 'Cannot generate report for a future date.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    location = LocationModel.objects.filter(id=location_id).first()
    if not location:
        return Response(
            {'status': 'error', 'message': 'Location not found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    # Initial generation if no rows exist
    if not DailyInventory.objects.filter(date=report_date, location=location).exists():
        location_ingredients = (LocationIngredient.objects
                                .select_related('master_ingredient', 'location')
                                .filter(location=location, is_assigned=True, is_available=True, master_ingredient__is_active=True))
        if not location_ingredients.exists():
            return Response(
                {'status': 'error', 'message': 'No ingredients found for this location.'},
                status=status.HTTP_404_NOT_FOUND
            )

        # get previous report entries
        latest_prev_rows = (
            DailyInventory.objects
            .filter(
                location=location,
                date__lt=report_date,
                location_ingredient__in=location_ingredients
            )
            .order_by('location_ingredient', '-date')
            .distinct('location_ingredient')
            .values('location_ingredient', 'closing_stock')
        )

        previous_map = {row['location_ingredient']: row for row in latest_prev_rows}

        new_entries = []
        for loc_ing in location_ingredients:
            prev_row = previous_map.get(loc_ing.id)
            opening_stock = prev_row['closing_stock'] if prev_row else 0.0

            new_entries.append(DailyInventory(
                date=report_date,
                location_ingredient=loc_ing,
                location=location,
                opening_stock=opening_stock,
                prepared_qty=0.0,
                used_qty=0.0,
                closing_stock=opening_stock,
                raw_equiv=None,
            ))

        with transaction.atomic():
            DailyInventory.objects.bulk_create(
                new_entries,
                ignore_conflicts=True
            )

    #  add any newly assigned ingredients missing from today’s report
    created_count = ensure_daily_rows(location, report_date)

    entries = (
        DailyInventory.objects
        .select_related('location_ingredient__master_ingredient', 'location')
        .filter(date=report_date, location=location, location_ingredient__master_ingredient__is_active=True)
        .order_by('location_ingredient__master_ingredient__name')
    )

    if not entries.exists():
        return Response(
            {'status': 'error', 'message': 'No inventory records found for this date.'},
            status=status.HTTP_404_NOT_FOUND
        )

    results = []
    for row in entries:
        if row.location_ingredient:
            results.append({
                "id": row.id,
                "date": row.date.strftime("%Y-%m-%d"),  # Convert date to string format
                "ingredient_id": row.location_ingredient.id,
                "ingredient_name": row.location_ingredient.master_ingredient.name,
                "location_id": row.location.id,
                "location_name": row.location.name,
                "is_composite": row.location_ingredient.master_ingredient.is_composite,
                "ingredient_unit": row.location_ingredient.master_ingredient.unit,
                "opening_stock": row.opening_stock,
                "prepared_qty": row.prepared_qty,
                "used_qty": row.used_qty,
                "closing_stock": row.closing_stock,
                "raw_equiv": row.raw_equiv,
            })

    response_data = {
        "status": "success",
        "data": results,
        "added_new_ingredients": created_count  # for UI toast
    }

    return Response(
        response_data,
        status=status.HTTP_200_OK
    )
