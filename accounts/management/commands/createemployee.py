from django.core.management.base import BaseCommand
from accounts.models import User


class Command(BaseCommand):
    help = "Create a new employee user"

    def handle(self, *args, **options):
        email = input("Email: ").strip()
        password = input("Password: ")

        if not email or not password:
            self.stderr.write("Email and password are required.")
            return

        if User.objects.filter(email=email).exists():
            self.stderr.write("A user with that email already exists.")
            return

        User.objects.create_user(
            email=email,
            password=password,
            role="employee",
        )
        self.stdout.write(self.style.SUCCESS(
            f"Employee '{email}' created successfully."))
