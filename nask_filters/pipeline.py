import logging
from openedx_filters import PipelineStep
from common.djangoapps.student.models import CourseEnrollment
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from crum import get_current_user 

log = logging.getLogger(__name__)

class AutoEnrollByCorpEmail(PipelineStep):
    """
    Przy logowaniu sprawdza domenę emaila i zapisuje na wszystkie kursy tej organizacji.
    Wersja ZOPTYMALIZOWANA (brak problemu N+1 zapytań SQL).
    """

    def run_filter(self, user, *args, **kwargs):
        # 0. Walidacja wstępna
        if not user.is_active:
            return {}

        # 1. Wyłuskanie "slugu" z maila
        try:
            if '@' not in user.email:
                return {}
            email_domain = user.email.split('@')[1] 
            # Zakładamy: domena 'nokia.com' -> organizacja 'nokia'
            org_slug = email_domain.split('.')[0]   
        except Exception as e:
            log.warning(f"[NASK] Błąd parsowania maila {user.email}: {e}")
            return {}

        # 2. Pobranie kursów organizacji
        # Pobieramy tylko te kursy, które pasują do slug-a
        courses_to_enroll = list(CourseOverview.objects.filter(org__iexact=org_slug))
        
        if not courses_to_enroll:
            # log.info(f"[NASK] Brak kursów dla organizacji: {org_slug}")
            return {}

        # 3. OPTYMALIZACJA: Pobieramy ID wszystkich aktywnych zapisów użytkownika JEDNYM zapytaniem.
        # Tworzymy zbiór (set) ID kursów, co pozwala na błyskawiczne sprawdzanie "in set".
        existing_enrollment_ids = set(
            CourseEnrollment.objects.filter(
                user=user, 
                is_active=True
            ).values_list('course_id', flat=True)
        )

        # 4. Pętla zapisu (sprawdzenie w RAM, zapis tylko gdy konieczne)
        for course in courses_to_enroll:
            if course.id in existing_enrollment_ids:
                # Użytkownik już ma ten kurs - pomijamy bez pytania bazy
                continue

            try:
                log.info(f"[NASK] Auto-zapisywanie {user.username} na {course.id}")
                CourseEnrollment.enroll(
                    user=user,
                    course_key=course.id,
                    mode="audit", # lub 'honor'
                    check_access=True
                )
            except Exception as e:
                log.error(f"[NASK] Błąd zapisu na {course.id}: {e}")

        return {}


class StampCoursesForDashboard(PipelineStep):
    """
    Modyfikuje dane kursu wysyłane do Dashboardu (MFE).
    Logika:
    1. Jeśli Admin/Staff -> ZAWSZE pokazuj (ustaw 'corp-auto-enrolled').
    2. Jeśli zwykły user -> Pokazuj tylko jeśli organizacja kursu == organizacja maila.
    """

    def run_filter(self, course_key, serialized_enrollment, *args, **kwargs):
        # 1. Pobieramy usera z aktualnego wątku (filtr nie przekazuje go w argumentach)
        user = get_current_user()
        
        if not user or not user.is_authenticated:
            return {}

        # --- ADMIN PASS ---
        # Jeśli użytkownik jest członkiem obsługi (is_staff) lub superuserem -> PRZEPUŚĆ WSZYSTKO
        if user.is_staff or user.is_superuser:
            # log.info(f"[NASK] Admin Access: Stempluję kurs {course_key} dla admina {user.username}")
            serialized_enrollment['mode'] = 'corp-auto-enrolled'
            return {
                "course_key": course_key,
                "serialized_enrollment": serialized_enrollment
            }
        # ------------------

        # 2. Logika dla zwykłego użytkownika
        
        # Pobieranie organizacji kursu
        try:
            course_org = course_key.org.lower()
        except AttributeError:
            # Fallback dla starszych wersji course_key
            course_org = str(course_key).split(':')[1].split('+')[0].lower()

        # Pobieranie organizacji usera
        try:
            if not user.email or '@' not in user.email:
                return {}
            user_org_slug = user.email.split('@')[1].split('.')[0].lower()
        except Exception:
            return {}

        # 3. Porównanie i Stemplowanie
        if course_org == user_org_slug:
            # log.info(f"[NASK] MATCH! Kurs {course_key} pasuje do organizacji {user_org_slug}.")
            
            # Ustawiamy flagę uzgodnioną z Frontendem
            serialized_enrollment['mode'] = 'corp-auto-enrolled'
            
            return {
                "course_key": course_key,
                "serialized_enrollment": serialized_enrollment
            }

        return {}