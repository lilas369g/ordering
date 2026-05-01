from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="DailySalesProcessing",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, db_index=True),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("processing_date", models.DateField(db_index=True, unique=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("in_progress", "In Progress"),
                            ("completed", "Completed"),
                            ("failed", "Failed"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("total_chunks", models.IntegerField(default=0)),
                ("processed_chunks", models.IntegerField(default=0)),
                ("failed_chunks", models.IntegerField(default=0)),
                ("last_processed_order_id", models.IntegerField(default=0)),
                (
                    "error_log",
                    models.TextField(
                        blank=True,
                        help_text="JSON-formatted list of failed chunks",
                    ),
                ),
            ],
            options={
                "db_table": "daily_sales_processing",
                "ordering": ["-processing_date"],
            },
        ),
    ]
