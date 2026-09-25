from django.db import migrations


def forwards(apps, schema_editor):
    from core.seed import seed_classifiers

    seed_classifiers(apps.get_model("core", "Classifier"))


class Migration(migrations.Migration):
    dependencies = [("core", "0001_initial")]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
