from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("racing", "0013_party_game_economy"),
    ]

    operations = [
        migrations.AlterField(
            model_name="itemdefinition",
            name="kind",
            field=models.CharField(
                choices=[
                    ("speed_tonic", "Speed tonic"),
                    ("guard_tonic", "Guard tonic"),
                    ("trip_tonic", "Trip tonic"),
                    ("confusion_tonic", "Confusion tonic"),
                    ("growth_tonic", "Growth tonic"),
                    ("shrink_tonic", "Shrink tonic"),
                    ("transform_tonic", "Transform tonic"),
                    ("fireproof_tonic", "Fireproof tonic"),
                    ("nitro_serum", "Nitro serum"),
                    ("recovery_brew", "Recovery brew"),
                    ("ghost_draught", "Ghost draught"),
                    ("second_wind", "Second wind"),
                    ("phoenix_flask", "Phoenix flask"),
                    ("banana", "Banana"),
                    ("pothole", "Pothole"),
                    ("oil_slick", "Oil slick"),
                    ("boost_pad", "Boost pad"),
                    ("boxing_glove", "Boxing glove"),
                    ("detour_sign", "Detour sign"),
                    ("speed_bump", "Speed bump"),
                    ("stop_sign", "Stop sign"),
                    ("glass_door", "Glass door"),
                    ("rock_wall", "Rock wall"),
                    ("roomba_vacuum", "Roomba vacuum"),
                    ("springboard", "Springboard"),
                    ("magnet_mine", "Magnet mine"),
                    ("portal_gate", "Portal gate"),
                ],
                max_length=20,
            ),
        ),
    ]
