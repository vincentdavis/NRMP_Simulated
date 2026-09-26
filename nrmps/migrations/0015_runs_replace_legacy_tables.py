# Plan step 2.3 and decision D3: the legacy v1 tables go; runs, their stages and artifacts, and uploaded
# populations replace them.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nrmps', '0014_convert_configurations'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='match',
            unique_together=None,
        ),
        migrations.RemoveField(
            model_name='match',
            name='school',
        ),
        migrations.RemoveField(
            model_name='match',
            name='simulation',
        ),
        migrations.RemoveField(
            model_name='match',
            name='student',
        ),
        migrations.RemoveField(
            model_name='school',
            name='simulation',
        ),
        migrations.RemoveField(
            model_name='simulationconfig',
            name='simulation',
        ),
        migrations.RemoveField(
            model_name='student',
            name='simulation',
        ),
        migrations.RemoveField(
            model_name='simulation',
            name='iterations',
        ),
        migrations.RemoveField(
            model_name='simulation',
            name='status',
        ),
        migrations.CreateModel(
            name='PopulationUpload',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('side', models.CharField(choices=[('applicants', 'Applicants'), ('programs', 'Programs')], max_length=20)),
                ('filename', models.CharField(blank=True, default='', max_length=255)),
                ('rows', models.PositiveIntegerField()),
                ('data', models.BinaryField(help_text='The parsed file as npz (nrmps.population_csv).')),
                ('digest', models.CharField(help_text='SHA-256 of `data`.', max_length=64)),
                ('uploaded_at', models.DateTimeField(auto_now_add=True)),
                ('simulation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='uploads', to='nrmps.simulation')),
            ],
        ),
        migrations.CreateModel(
            name='SimulationRun',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('number', models.PositiveIntegerField(help_text='1, 2, 3 ... within the simulation.')),
                ('status', models.CharField(choices=[('queued', 'Queued'), ('running', 'Running'), ('succeeded', 'Finished'), ('failed', 'Failed')], default='queued', max_length=20)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('started_at', models.DateTimeField(blank=True, null=True)),
                ('finished_at', models.DateTimeField(blank=True, null=True)),
                ('duration_ms', models.PositiveIntegerField(blank=True, help_text='Engine time, start to finish.', null=True)),
                ('params', models.JSONField(help_text='The parameters, with the seed that was used.')),
                ('params_hash', models.CharField(max_length=64)),
                ('seed', models.BigIntegerField()),
                ('seed_was_drawn', models.BooleanField(default=False, help_text='The draft had no seed, so one was drawn.')),
                ('replicate', models.PositiveIntegerField(default=0)),
                ('population_source', models.JSONField(default=dict, help_text='Per side: "generated" or the uploaded file name.')),
                ('population_digest', models.CharField(blank=True, default='', max_length=64)),
                ('fingerprints', models.JSONField(default=dict, help_text='Per stage: a hash of everything the stage depends on.')),
                ('n_applicants', models.PositiveIntegerField(default=0)),
                ('n_programs', models.PositiveIntegerField(default=0)),
                ('n_positions', models.PositiveIntegerField(default=0)),
                ('model_version', models.CharField(max_length=20)),
                ('engine_version', models.CharField(max_length=20)),
                ('schema_version', models.PositiveSmallIntegerField()),
                ('app_version', models.CharField(max_length=20)),
                ('git_sha', models.CharField(blank=True, default='', max_length=40)),
                ('numpy_version', models.CharField(max_length=20)),
                ('python_version', models.CharField(max_length=20)),
                ('metrics', models.JSONField(blank=True, null=True)),
                ('error', models.TextField(blank=True, default='')),
                ('progress_done', models.PositiveBigIntegerField(default=0)),
                ('progress_total', models.PositiveBigIntegerField(default=0)),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
                ('simulation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='runs', to='nrmps.simulation')),
            ],
            options={
                'ordering': ['-number'],
            },
        ),
        migrations.CreateModel(
            name='RunArtifact',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('kind', models.CharField(choices=[('population', 'Population'), ('pre_interview', 'Pre-interview results')], max_length=30)),
                ('data', models.BinaryField()),
                ('size', models.PositiveIntegerField()),
                ('sha256', models.CharField(max_length=64)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('run', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='artifacts', to='nrmps.simulationrun')),
            ],
        ),
        migrations.CreateModel(
            name='StageRun',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('stage', models.CharField(choices=[('population', 'Population'), ('pre_interview', 'Pre-interview'), ('applications', 'Applications'), ('signals', 'Signals'), ('invitations', 'Invitations'), ('interviews', 'Interviews'), ('rank_lists', 'Rank order lists'), ('match', 'Match')], max_length=20)),
                ('status', models.CharField(choices=[('queued', 'Queued'), ('running', 'Running'), ('succeeded', 'Finished'), ('failed', 'Failed')], max_length=20)),
                ('fingerprint', models.CharField(max_length=64)),
                ('started_at', models.DateTimeField(blank=True, null=True)),
                ('finished_at', models.DateTimeField(blank=True, null=True)),
                ('duration_ms', models.PositiveIntegerField(blank=True, null=True)),
                ('counts', models.JSONField(blank=True, default=dict)),
                ('error', models.TextField(blank=True, default='')),
                ('run', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='stages', to='nrmps.simulationrun')),
            ],
        ),
        migrations.DeleteModel(
            name='Interview',
        ),
        migrations.DeleteModel(
            name='Match',
        ),
        migrations.DeleteModel(
            name='School',
        ),
        migrations.DeleteModel(
            name='SimulationConfig',
        ),
        migrations.DeleteModel(
            name='Student',
        ),
        migrations.AddConstraint(
            model_name='populationupload',
            constraint=models.UniqueConstraint(fields=('simulation', 'side'), name='one_upload_per_side'),
        ),
        migrations.AddIndex(
            model_name='simulationrun',
            index=models.Index(fields=['status', 'created_at'], name='run_status_created'),
        ),
        migrations.AddConstraint(
            model_name='simulationrun',
            constraint=models.UniqueConstraint(fields=('simulation', 'number'), name='unique_run_number'),
        ),
        migrations.AddConstraint(
            model_name='simulationrun',
            constraint=models.UniqueConstraint(condition=models.Q(('status__in', ['queued', 'running'])), fields=('simulation',), name='one_active_run_per_simulation'),
        ),
        migrations.AddConstraint(
            model_name='runartifact',
            constraint=models.UniqueConstraint(fields=('run', 'kind'), name='unique_artifact_kind_per_run'),
        ),
        migrations.AddConstraint(
            model_name='stagerun',
            constraint=models.UniqueConstraint(fields=('run', 'stage'), name='unique_stage_per_run'),
        ),
    ]
