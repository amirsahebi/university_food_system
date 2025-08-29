#!/bin/bash

# Run Django tests for all Celery tasks
echo "Running Celery task tests..."
echo "========================================"

# Run users app tests
echo "Testing users app tasks..."
python manage.py test users.tests.test_tasks -v 2
echo ""

# Run payments app tests
echo "Testing payments app tasks..."
python manage.py test payments.tests.test_tasks -v 2
echo ""

# Run background tasks tests
echo "Testing background tasks..."
python manage.py test university_food_system.tests.test_background_tasks -v 2
echo ""

echo "========================================"
echo "All Celery task tests completed!"
