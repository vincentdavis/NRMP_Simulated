# Plan step 2.3: simulations get model 2.0 parameters (converted from their configuration in 0014).

import nrmps.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nrmps', '0012_applicant_program_names_and_dead_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='simulation',
            name='params',
            field=models.JSONField(default=nrmps.models.default_params, help_text='The draft parameters (schema v1 of nrmps.params); runs copy them.'),
        ),
        migrations.AddField(
            model_name='simulation',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
    ]
