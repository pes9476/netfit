"""Align recognizable historical IDs; never delete rows or replace explicit IDs."""
import hashlib
import re
import unicodedata

from django.db import migrations


def normalize(value):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value or "").strip().lower())


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def align_ids(apps, schema_editor):
    Facility = apps.get_model("fitness", "Facility")
    manager = Facility.objects.using(schema_editor.connection.alias)
    # Load bounded columns once so collisions across batches are recognized.
    rows = list(manager.order_by("pk").values_list("pk", "name", "address", "source_record_id"))
    occupied = {key for _, _, _, key in rows if key}
    batch = []
    changed = conflicts = 0
    for pk, name, address, key in rows:
        name, address = normalize(name), normalize(address)
        # Legacy duplicate keys and external-source keys must be preserved.
        if not name or key != digest(f"{name}|{address}"):
            continue
        target = digest(f"name:{name}|address:{address}")
        if target in occupied:
            conflicts += 1
            continue
        occupied.add(target)
        batch.append(Facility(pk=pk, source_record_id=target))
        changed += 1
        if len(batch) == 500:
            manager.bulk_update(batch, ["source_record_id"], batch_size=500)
            batch.clear()
            print(f"[0023] aligned {changed} IDs (commit pending)", flush=True)
    if batch:
        manager.bulk_update(batch, ["source_record_id"], batch_size=500)
    print(f"[0023] aligned={changed}, existing canonical conflicts preserved={conflicts}", flush=True)


class Migration(migrations.Migration):
    dependencies = [("fitness", "0022_facility_source_record_id_unique")]
    operations = [migrations.RunPython(align_ids, migrations.RunPython.noop)]
