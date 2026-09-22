import hashlib
import re
import unicodedata

from django.db import migrations


def normalize(value):
    value = unicodedata.normalize("NFKC", value or "").strip().lower()
    return re.sub(r"\s+", " ", value)


def backfill_source_record_ids(apps, schema_editor):
    Facility = apps.get_model("fitness", "Facility")
    used = set()
    for facility in Facility.objects.order_by("pk").iterator():
        identity = f"{normalize(facility.name)}|{normalize(facility.address)}"
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
        if digest in used:
            digest = hashlib.sha256(
                f"legacy:{facility.pk}:{identity}".encode("utf-8")
            ).hexdigest()
        used.add(digest)
        facility.source_record_id = digest
        facility.save(update_fields=["source_record_id"])


class Migration(migrations.Migration):
    dependencies = [("fitness", "0020_facility_source_record_id_datasyncrun")]

    operations = [migrations.RunPython(backfill_source_record_ids, migrations.RunPython.noop)]
