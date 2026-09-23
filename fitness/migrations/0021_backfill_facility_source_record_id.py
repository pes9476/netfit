import hashlib
import re
import unicodedata

from django.db import migrations


def normalize(value):
    value = unicodedata.normalize("NFKC", value or "").strip().lower()
    return re.sub(r"\s+", " ", value)


def backfill_source_record_ids(apps, schema_editor):
    Facility = apps.get_model("fitness", "Facility")
    facilities = Facility.objects.using(schema_editor.connection.alias)
    used = set()
    last_pk = None
    processed = 0
    # Keyset pagination avoids a long-lived server-side cursor on poolers.
    # Keep historical ID semantics: deployed databases may already use them.
    while True:
        query = facilities.order_by("pk")
        if last_pk is not None:
            query = query.filter(pk__gt=last_pk)
        batch = list(query.only("pk", "name", "address", "source_record_id")[:500])
        if not batch:
            break
        for facility in batch:
            identity = f"{normalize(facility.name)}|{normalize(facility.address)}"
            digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
            if digest in used:
                digest = hashlib.sha256(
                    f"legacy:{facility.pk}:{identity}".encode("utf-8")
                ).hexdigest()
            used.add(digest)
            facility.source_record_id = digest
        facilities.bulk_update(batch, ["source_record_id"], batch_size=500)
        last_pk = batch[-1].pk
        processed += len(batch)
        print(f"[0021] processed {processed} facilities (commit pending)", flush=True)


class Migration(migrations.Migration):
    dependencies = [("fitness", "0020_facility_source_record_id_datasyncrun")]

    operations = [migrations.RunPython(backfill_source_record_ids, migrations.RunPython.noop)]
