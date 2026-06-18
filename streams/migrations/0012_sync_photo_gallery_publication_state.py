from django.db import migrations


def sync_photo_gallery_publication_state(apps, schema_editor):
    PhotoGallery = apps.get_model('streams', 'PhotoGallery')
    PhotoGallery.objects.filter(moderation_status='approved').update(is_active=True)
    PhotoGallery.objects.filter(moderation_status__in=('rejected', 'suspended')).update(is_active=False)


def reverse_sync_photo_gallery_publication_state(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('streams', '0011_photogallery_photogalleryimage'),
    ]

    operations = [
        migrations.RunPython(sync_photo_gallery_publication_state, reverse_sync_photo_gallery_publication_state),
    ]
