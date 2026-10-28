from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import User
from monitoring.models import Device, EscalationChain, Fridge

DEMO_PASSWORD = "Demo-ColdChain-2026"

DEMO_USERS = [
    ("n1@coldchain.local", "Responsable", "Frigo", User.Role.RESPONSIBLE, 1),
    ("n2@coldchain.local", "Supérieur", "Labo", User.Role.SUPERVISOR, 2),
    ("n3@coldchain.local", "Admin", "Labo", User.Role.ADMIN, 3),
]


class Command(BaseCommand):
    help = "Crée des données de démonstration : 3 utilisateurs (N1/N2/N3), un frigo et son nœud."

    @transaction.atomic
    def handle(self, *args, **options):
        fridge, _ = Fridge.objects.get_or_create(
            name="Frigo Labo 01", defaults={"location": "Salle de biologie"}
        )

        for email, first_name, last_name, role, level in DEMO_USERS:
            user, created = User.objects.get_or_create(
                email=email,
                defaults={"first_name": first_name, "last_name": last_name, "role": role},
            )
            if created:
                user.set_password(DEMO_PASSWORD)
                user.save()
            EscalationChain.objects.get_or_create(fridge=fridge, level=level, user=user)

        device, created = Device.objects.get_or_create(
            device_id="FRIGO-LAB-01", defaults={"fridge": fridge}
        )
        if created:
            raw_key = device.rotate_api_key()
            device.save()
            self.stdout.write(self.style.WARNING(f"Clé API du nœud FRIGO-LAB-01 : {raw_key}"))
        else:
            self.stdout.write("Nœud FRIGO-LAB-01 déjà existant (clé inchangée).")

        self.stdout.write(
            self.style.SUCCESS(
                f"Données de démo prêtes. Comptes : {', '.join(u[0] for u in DEMO_USERS)} "
                f"/ mot de passe : {DEMO_PASSWORD}"
            )
        )
