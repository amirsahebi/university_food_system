import requests
import json
import subprocess
import sys

BASE_URL = "https://javan-foods.ir"
TEST_PHONE = "09990000001"
TEST_STUDENT_ID = "999000001"
TEST_PASSWORD = "TestPassword@2026"

session = requests.Session()
results = []

def record(name, passed, detail=""):
    results.append((name, passed, detail))
    status_str = "[PASS]" if passed else "[FAIL]"
    print(f"  {status_str} {name}: {detail}")

print("=" * 60)
print("STARTING END-TO-END DEPLOYMENT & INTEGRATION TESTS")
print("Target:", BASE_URL)
print("=" * 60)

# 1. Frontend routes & PWA & Assets
frontend_tests = [
    ("Landing Page", "/", 200),
    ("Student Dashboard", "/student-dashboard", 200),
    ("Payment History", "/payment/history", 200),
    ("Admin Dashboard", "/admin-dashboard", 200),
    ("PWA Manifest", "/manifest.webmanifest", 200),
    ("Admin Static Base CSS", "/static/admin/css/base.css", 200),
    ("Branded Cartoon Dish Image", "/media/foods/clean_dish_cartoon_branded.jpg", 200),
    ("Branded Joojeh Kabab Image", "/media/foods/branded_joojeh_kabab.jpg", 200),
    ("Branded Zereshk Polo Image", "/media/foods/branded_zereshk_polo.jpg", 200),
    ("Branded Pizza Pepperoni Image", "/media/foods/branded_pizza_pepperoni.jpg", 200),
    ("Branded Burger Beef Image", "/media/foods/branded_burger_beef.jpg", 200),
]

for name, path, expected_status in frontend_tests:
    try:
        r = session.get(BASE_URL + path, timeout=10)
        record(name, r.status_code == expected_status, f"HTTP {r.status_code}")
    except Exception as e:
        record(name, False, f"Exception: {e}")

# 2. Celery Worker & Beat Status
try:
    c_inspect = subprocess.check_output(
        "docker exec university_food_system-celery-worker celery -A university_food_system inspect ping",
        shell=True, text=True, timeout=15
    )
    record("Celery Worker Ping", "pong" in c_inspect.lower(), "pong response received" if "pong" in c_inspect.lower() else c_inspect.strip())
except Exception as e:
    record("Celery Worker Ping", False, str(e))

# 3. Database user count check
get_count_script = (
    "import django, os, sys; "
    "sys.path.insert(0, '/app'); "
    "os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'university_food_system.settings'); "
    "django.setup(); "
    "from users.models import User; "
    "print('USER_COUNT:', User.all_objects.count())"
)

try:
    out = subprocess.check_output(
        ["docker", "exec", "university_food_system-web", "python", "-c", get_count_script],
        text=True
    )
    initial_count = int(out.strip().split("USER_COUNT:")[1].strip())
    record("Database Initial User Count", True, f"{initial_count} users present")
except Exception as e:
    record("Database Initial User Count", False, str(e))
    initial_count = None

# 4. Create Ephemeral Test User, Run Scenarios, Clean Up
create_script = (
    "import django, os, sys; "
    "sys.path.insert(0, '/app'); "
    "os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'university_food_system.settings'); "
    "django.setup(); "
    "from users.models import User; "
    f"User.all_objects.filter(phone_number='{TEST_PHONE}').delete(); "
    "user = User.objects.create_user("
    f"    phone_number='{TEST_PHONE}', "
    f"    student_number='{TEST_STUDENT_ID}', "
    "    first_name='کاربر تست', "
    "    last_name='سیستم خودکار', "
    "    role='student'"
    "); "
    f"user.set_password('{TEST_PASSWORD}'); "
    "user.save(); "
    "print('USER_CREATED_ID:', user.id)"
)

cleanup_script = (
    "import django, os, sys; "
    "sys.path.insert(0, '/app'); "
    "os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'university_food_system.settings'); "
    "django.setup(); "
    "from users.models import User; "
    f"deleted, _ = User.all_objects.filter(phone_number='{TEST_PHONE}').delete(); "
    "print('USER_DELETED_COUNT:', deleted); "
    "print('FINAL_USER_COUNT:', User.all_objects.count())"
)

try:
    # Create user
    out = subprocess.check_output(
        ["docker", "exec", "university_food_system-web", "python", "-c", create_script],
        text=True
    )
    record("Ephemeral User Creation", "USER_CREATED_ID:" in out, "Created test user successfully")

    # Signin through Nginx reverse proxy
    login_url = f"{BASE_URL}/api/auth/signin/"
    login_payload = {
        "phone_number": TEST_PHONE,
        "password": TEST_PASSWORD
    }
    r = session.post(login_url, json=login_payload, timeout=10)
    record("API Signin (/api/auth/signin/)", r.status_code == 200, f"HTTP {r.status_code}")

    if r.status_code == 200:
        data = r.json()
        access_token = data.get("access_token") or data.get("access")
        refresh_token = data.get("refresh_token") or data.get("refresh")
        record("JWT Access Token Generated", bool(access_token), "Token received")

        headers = {
            "Authorization": f"Bearer {access_token}"
        }

        # Protected route: /api/auth/me/
        r_me = session.get(f"{BASE_URL}/api/auth/me/", headers=headers, timeout=10)
        record("API Profile (/api/auth/me/)", r_me.status_code == 200, f"HTTP {r_me.status_code}")

        # Protected route: /api/auth/trust-score/
        r_trust = session.get(f"{BASE_URL}/api/auth/trust-score/", headers=headers, timeout=10)
        record("API Trust Score (/api/auth/trust-score/)", r_trust.status_code == 200, f"HTTP {r_trust.status_code}")

        # Protected route: /api/foods/
        r_foods = session.get(f"{BASE_URL}/api/foods/", headers=headers, timeout=10)
        foods_data = r_foods.json() if r_foods.status_code == 200 else []
        foods_count = len(foods_data) if isinstance(foods_data, list) else 0
        record("API Foods List (/api/foods/)", r_foods.status_code == 200, f"HTTP {r_foods.status_code} - Total foods: {foods_count}")

        # Protected route: /api/foods/categories/
        r_cats = session.get(f"{BASE_URL}/api/foods/categories/", headers=headers, timeout=10)
        record("API Food Categories (/api/foods/categories/)", r_cats.status_code == 200, f"HTTP {r_cats.status_code}")

        # Protected route: /api/core/voucher-types/
        r_vouchers = session.get(f"{BASE_URL}/api/core/voucher-types/", headers=headers, timeout=10)
        record("API Voucher Types (/api/core/voucher-types/)", r_vouchers.status_code == 200, f"HTTP {r_vouchers.status_code}")

        # Protected route: /api/orders/student/
        r_res = session.get(f"{BASE_URL}/api/orders/student/", headers=headers, timeout=10)
        record("API Student Orders (/api/orders/student/)", r_res.status_code == 200, f"HTTP {r_res.status_code}")

        # Protected route: /api/payments/history/
        r_pay = session.get(f"{BASE_URL}/api/payments/history/", headers=headers, timeout=10)
        record("API Payment History (/api/payments/history/)", r_pay.status_code == 200, f"HTTP {r_pay.status_code}")

        # Token Refresh
        r_ref = session.post(f"{BASE_URL}/api/auth/refresh/", json={"refresh": refresh_token, "refresh_token": refresh_token}, timeout=10)
        record("API Token Refresh (/api/auth/refresh/)", r_ref.status_code == 200, f"HTTP {r_ref.status_code}")

        # Signout / Blacklist
        r_out = session.post(f"{BASE_URL}/api/auth/signout/", json={"refresh_token": refresh_token}, headers=headers, timeout=10)
        record("API Signout (/api/auth/signout/)", r_out.status_code in [200, 204, 205], f"HTTP {r_out.status_code}")

except Exception as e:
    record("API Scenario Exception", False, str(e))
finally:
    # Clean up test user
    try:
        clean_out = subprocess.check_output(
            ["docker", "exec", "university_food_system-web", "python", "-c", cleanup_script],
            text=True
        )
        final_count = int(clean_out.strip().split("FINAL_USER_COUNT:")[1].strip())
        record("Database Cleanup Verification", final_count == initial_count, f"Original: {initial_count}, Current: {final_count}")
    except Exception as e:
        record("Database Cleanup Verification", False, f"Failed cleanup: {e}")

print("=" * 60)
failed_tests = [t for t in results if not t[1]]
if not failed_tests:
    print(f"ALL {len(results)} TESTS PASSED SUCCESSFULLY! ZERO RESIDUAL TEST DATA.")
else:
    print(f"FAILED {len(failed_tests)} OF {len(results)} TESTS:")
    for f in failed_tests:
        print(f"  FAILED: {f[0]} - {f[2]}")
print("=" * 60)
