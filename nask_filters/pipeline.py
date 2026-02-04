import logging
from openedx_filters import PipelineStep
from common.djangoapps.student.models import CourseEnrollment
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from crum import get_current_user 


# Ustawiamy logger
log = logging.getLogger(__name__)

class AutoEnrollByCorpEmail(PipelineStep):
    """
    Przy logowaniu sprawdza domenę emaila i zapisuje na wszystkie kursy tej organizacji.
    Wersja z HEAVY DEBUGGING.
    """

    def run_filter(self, user, *args, **kwargs):
        log.info(f"[NASK-DEBUG] --- START AutoEnrollByCorpEmail ---")
        log.info(f"[NASK-DEBUG] User: {user.username}, Email: {user.email}, IsActive: {user.is_active}")

        if not user.is_active:
            log.info("[NASK-DEBUG] Użytkownik nieaktywny. Przerywam.")
            return {}

        # 1. Wyłuskanie "slugu" z maila
        try:
            if '@' not in user.email:
                log.warning(f"[NASK-DEBUG] Błędny format emaila (brak @): {user.email}")
                return {}
                
            email_domain = user.email.split('@')[1] # np. nokia.com
            # UWAGA: Tutaj założenie, że nazwa firmy to pierwsza część domeny
            org_slug = email_domain.split('.')[0]   # np. nokia
            
            log.info(f"[NASK-DEBUG] Parsowanie emaila: Domena='{email_domain}' -> OrgSlug='{org_slug}'")
        except Exception as e:
            log.exception(f"[NASK-DEBUG] CRITICAL ERROR przy parsowaniu emaila: {e}")
            return {}

        # 2. Pobranie kursów z bazy danych
        try:
            log.info(f"[NASK-DEBUG] Szukam kursów dla org__iexact='{org_slug}' w modelu CourseOverview...")
            
            # Pobieramy tylko ID, żeby nie zapychać pamięci, jeśli kursów jest 1000
            courses_to_enroll = CourseOverview.objects.filter(org__iexact=org_slug)
            count = courses_to_enroll.count()
            
            log.info(f"[NASK-DEBUG] Znaleziono {count} kursów pasujących do organizacji '{org_slug}'.")
            
            if count == 0:
                log.info("[NASK-DEBUG] Brak kursów. Kończę filtr.")
                return {}

        except Exception as e:
            log.exception(f"[NASK-DEBUG] Błąd przy odpytywaniu bazy danych o kursy: {e}")
            return {}

        # 3. Zapisywanie użytkownika
        enrolled_count = 0
        already_enrolled_count = 0

        for course in courses_to_enroll:
            course_id_str = str(course.id)
            try:
                # Sprawdź czy już nie jest zapisany
                is_enrolled = CourseEnrollment.is_enrolled(user, course.id)
                
                if is_enrolled:
                    already_enrolled_count += 1
                    # Odkomentuj linię niżej, jeśli chcesz widzieć każdy pominięty kurs (dużo logów)
                    # log.info(f"[NASK-DEBUG] User {user.username} już zapisany na {course_id_str}. Pomijam.")
                else:
                    log.info(f"[NASK-DEBUG] PRÓBA zapisu użytkownika {user.username} na kurs {course_id_str}...")
                    CourseEnrollment.enroll(
                        user=user,
                        course_key=course.id,
                        mode="audit", # lub 'honor'
                        check_access=True
                    )
                    log.info(f"[NASK-DEBUG] SUKCES: Zapisano na {course_id_str}")
                    enrolled_count += 1

            except Exception as e:
                log.error(f"[NASK-DEBUG] BŁĄD przy zapisywaniu na kurs {course_id_str}: {e}")

        log.info(f"[NASK-DEBUG] Podsumowanie: Nowych zapisów: {enrolled_count}, Było już zapisanych: {already_enrolled_count}")
        log.info(f"[NASK-DEBUG] --- END AutoEnrollByCorpEmail ---")
        
        return {}



class StampCoursesForDashboard(PipelineStep):
    """
    Modyfikuje dane kursu wysyłane do Dashboardu (MFE).
    Zmienia 'mode' na 'corp-auto-enrolled' (POPRAWIONA WERSJA).
    """

    def run_filter(self, course_key, serialized_enrollment, *args, **kwargs):
        # 1. Pobieramy usera z aktualnego wątku (bo filtr go nie przekazuje w argumentach)
        user = get_current_user()
        
        # Logowanie startowe - sprawdźmy czy filtr w ogóle ruszył
        log.info(f"[NASK-DEBUG] [Stamp] Uruchomiono dla kursu: {course_key}")

        if not user or not user.is_authenticated:
            log.warning("[NASK-DEBUG] [Stamp] Brak zalogowanego użytkownika.")
            return {}

        # 2. Pobieramy organizację kursu z course_key (obiekt CourseKey)
        try:
            course_org = course_key.org.lower()
        except AttributeError:
            # Fallback gdyby course_key był stringiem (rzadkie, ale możliwe)
            course_org = str(course_key).split(':')[1].split('+')[0].lower()

        # 3. Pobieramy organizację użytkownika z maila
        try:
            if not user.email or '@' not in user.email:
                return {}
            user_org_slug = user.email.split('@')[1].split('.')[0].lower()
        except Exception as e:
            log.warning(f"[NASK-DEBUG] [Stamp] Błąd parsowania maila: {e}")
            return {}

        # 4. Porównanie i Stemplowanie
        if course_org == user_org_slug:
            log.info(f"[NASK-DEBUG] [Stamp] MATCH! Kurs {course_key} pasuje do organizacji {user_org_slug}. Zmieniam mode.")
            
            # W tym filtrze edytujemy 'serialized_enrollment', który jest słownikiem
            serialized_enrollment['mode'] = 'corp-auto-enrolled'
            
            # Musimy zwrócić dokładnie te nazwy argumentów, które przyszły na wejście
            return {
                "course_key": course_key,
                "serialized_enrollment": serialized_enrollment
            }

        return {}
