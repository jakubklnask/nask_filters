# nask_filters/signals.py
import logging
from django.dispatch import receiver
from django.db.models.signals import post_save
from django.contrib.auth import get_user_model
from common.djangoapps.student.models import CourseEnrollment
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview

log = logging.getLogger(__name__)
User = get_user_model()

@receiver(post_save, sender=User)
def auto_enroll_on_creation(sender, instance, created, **kwargs):
    """
    Ta funkcja uruchamia się AUTOMATYCZNIE za każdym razem, gdy zapisywany jest User.
    Parametr 'created' jest True tylko wtedy, gdy to NOWY użytkownik (rejestracja).
    """
    if not created:
        return

    user = instance
    log.info(f"[NASK-SIGNAL] Wykryto utworzenie nowego użytkownika: {user.username}. Rozpoczynam auto-zapis.")

    # 1. Walidacja maila
    if not user.email or '@' not in user.email:
        return

    # 2. Wyłuskanie organizacji
    try:
        email_domain = user.email.split('@')[1] 
        org_slug = email_domain.split('.')[0]   
    except Exception as e:
        log.warning(f"[NASK-SIGNAL] Błąd parsowania maila: {e}")
        return

    # 3. Pobranie kursów
    courses_to_enroll = list(CourseOverview.objects.filter(org__iexact=org_slug))
    
    if not courses_to_enroll:
        log.info(f"[NASK-SIGNAL] Brak kursów dla organizacji: {org_slug}")
        return

    # 4. Zapisywanie (Tutaj nie musimy sprawdzać 'existing', bo user jest nowy i pusty!)
    for course in courses_to_enroll:
        try:
            log.info(f"[NASK-SIGNAL] Auto-zapisywanie nowego usera {user.username} na {course.id}")
            CourseEnrollment.enroll(
                user=user,
                course_key=course.id,
                mode="audit", # lub 'honor'
                check_access=True
            )
        except Exception as e:
            log.error(f"[NASK-SIGNAL] Błąd zapisu: {e}")