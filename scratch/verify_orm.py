import os
import django
from datetime import timedelta
from django.utils import timezone
from django.db.models import Count, Avg, Q, F
from django.db.models.functions import TruncMonth

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'acco.settings')
django.setup()

from base.models import Employer, Registration, JobOpening, ContactEvent, Skill

def verify():
    now = timezone.now()
    trend_start = now - timedelta(days=180)
    
    print(f"Trend start: {trend_start}")
    
    try:
        # Test Registration trends
        monthly_rows = (
            Registration.objects
            .filter(created_at__gte=trend_start)
            .annotate(month=TruncMonth('created_at'))
            .values('month')
            .annotate(count=Count('id'))
            .order_by('month')
        )
        print(f"Monthly rows: {list(monthly_rows)}")
        
        # Test Profile score aggregation
        # Registration has profile_score?
        fields = [f.name for f in Registration._meta.get_fields()]
        print(f"Registration fields: {fields}")
        
        if 'profile_score' in fields:
            profile_dist = Registration.objects.aggregate(
                b1=Count('id', filter=Q(profile_score__lte=40)),
                b2=Count('id', filter=Q(profile_score__gte=41, profile_score__lte=70)),
                b3=Count('id', filter=Q(profile_score__gte=71))
            )
            print(f"Profile dist: {profile_dist}")
        
        # Test ContactEvent joins
        contacts = (
            ContactEvent.objects
            .annotate(candidate_name=F('candidate__name'))
            .values('candidate_id', 'candidate_name')
            .annotate(contact_count=Count('id'))
            .order_by('-contact_count')[:5]
        )
        print(f"Contacts list: {list(contacts)}")
        
        print("ORM Check Passed")
    except Exception as e:
        print(f"ORM Check Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    verify()
