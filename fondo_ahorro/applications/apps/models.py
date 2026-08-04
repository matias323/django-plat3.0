from django.db import models

from core.models.base import BaseModel


# Create your models here.



class App(BaseModel):
    name = models.CharField(
                            verbose_name="Nombre de Aplicación",
                            max_length=255,
                            blank=False,
                            null=False,
                            )
    url = models.CharField(
                            verbose_name="URL de Aplicación",
                            max_length=255,
                            blank=False,
                            null=False,
                            )
    has_daughter = models.BooleanField(
                                    verbose_name="Tiene Hijas ?",
                                    default=False,
                                    null=False,
                                    blank=False,
                                    )
    order = models.IntegerField(
                                verbose_name="Orden",
                                null=False,
                                default=1,
                                blank=False,
                                )
    father_app = models.ForeignKey(
                                "self",
                                on_delete=models.SET_NULL,
                                null=True,
                                verbose_name="Aplicación Padre",
                                related_name="sub_apps",
                                blank=True,
                                )
    class Meta:
        db_table = "core_app"
        verbose_name = "Aplicación"
        verbose_name_plural = "Aplicaciones"

    def __str__(self):
        if self.father_app:
            return f"{self.name}  | App Padre: {self.father_app.name}"
        return self.name

    def get_apps_hijas(self):
        return self.father_app.sub_apps.all()

    @classmethod
    def get_navbar_menu(cls, user, session_role):
        """
        Retorna las aplicaciones padre permitidas para el usuario y rol activos,
        pre-cargando de manera eficiente sus respectivas aplicaciones hijas.
        """
        # 1. Filtramos las aplicaciones que el usuario tiene permitidas a través de su rol/permisos
        allowed_apps_queryset = cls.objects.filter(
            userpermission__is_active=True,
            roleapp__role=session_role,
            roleapp__role__roleuser__user=user,
            roleapp__is_active=True
        ).distinct()

        # 2. Obtenemos solo las apps Raíz (Padres), inyectándoles sus hijas ya filtradas mediante un Prefetch
        return cls.objects.filter(
            id__in=allowed_apps_queryset.values_list('id', flat=True),
            father_app__isnull=True
        ).prefetch_related(
            models.Prefetch(
                'sub_apps',
                queryset=allowed_apps_queryset.order_by('order'),
                to_attr='allowed_daughters' # Guardamos las hijas filtradas en este atributo
            )
        ).order_by('order')
    @classmethod
    def get_app_by_request(cls, request):
        """
        Identifica la App actual comparando el namespace/nombre de la vista
        """
        # if not request.resolver_match:
        #     return None

        #Buscar por el nombre completo de la URL/vista (ej. 'core:home' o 'devolucion:solicitud')
        view_name = request.resolver_match.view_name
        app = cls.objects.filter(
                            url=view_name,
                            # userpermission__app__url=view_name,
                            # userpermission__is_active=True,
                            ).first()
        if app:
            return app

