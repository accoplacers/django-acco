from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('base', '0010_employerinterest'),
    ]

    operations = [
        migrations.CreateModel(
            name='EmployeeInterest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('employee', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='job_interests', to='base.registration')),
                ('job', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='employee_interests', to='base.jobopening')),
            ],
            options={
                'unique_together': {('employee', 'job')},
            },
        ),
    ]
