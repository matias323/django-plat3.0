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
        Retorna las aplicaciones padre permitidas para el usuario y rol activos.
        Oculta los padres cuyos submódulos (hijas/nietas) queden vacíos por falta de permisos.
        """
        # 1. Filtramos las aplicaciones que el usuario tiene permitidas
        allowed_apps_queryset = cls.objects.filter(
            userpermission__is_active=True,
            roleapp__role=session_role,
            roleapp__role__roleuser__user=user,
            roleapp__is_active=True
        ).distinct()

        # 2. Prefetch de NIETAS: se guarda en 'allowed_daughters' dentro de cada HIJA
        prefetch_granddaughters = models.Prefetch(
            'sub_apps',
            queryset=allowed_apps_queryset.order_by('order'),
            to_attr='allowed_daughters'
        )

        # 3. Prefetch de HIJAS: cargamos sus 'sub_apps' usando el prefetch de NIETAS anidado
        prefetch_daughters = models.Prefetch(
            'sub_apps',
            queryset=allowed_apps_queryset.prefetch_related(prefetch_granddaughters).order_by('order'),
            to_attr='allowed_daughters'
        )

        # 4. Traemos todas las aplicaciones PADRE permitidas
        parents = cls.objects.filter(
            id__in=allowed_apps_queryset.values_list('id', flat=True),
            father_app__isnull=True,
            userpermission__is_active=True
        ).prefetch_related(
            prefetch_daughters
        ).distinct().order_by('order')

        # 5. Filtrado jerárquico en memoria
        visible_parents = []

        for father in parents:
            visible_daughters = []
            for daughter in getattr(father, 'allowed_daughters', []):
                # Verificamos si esta hija en la BDD tiene definidas nietas estructuradas
                has_db_granddaughters = daughter.sub_apps.exists()

                if has_db_granddaughters:
                    # Si en BDD tiene nietas, sólo mantenemos la hija si conserva al menos una nieta con permiso
                    if getattr(daughter, 'allowed_daughters', []):
                        visible_daughters.append(daughter)
                else:
                    # Si en BDD la hija NO tiene nietas por estructura, se mantiene directamente
                    visible_daughters.append(daughter)

            # Actualizamos la lista de hijas permitidas en el padre
            father.allowed_daughters = visible_daughters

            # Evaluamos el Padre:
            # Verificamos si el padre en la BDD tiene definidas hijas estructuradas
            has_db_daughters = father.sub_apps.exists()

            if has_db_daughters:
                # Si el padre tiene estructura de hijas, sólo se muestra si le quedó al menos una hija visible
                if visible_daughters:
                    visible_parents.append(father)
            else:
                # Si el padre es un módulo directo sin hijas, se muestra siempre que tenga permiso
                visible_parents.append(father)

        return visible_parents


    @classmethod
    def get_app_by_request(cls, request):
        """
        Identifica la App actual comparando el namespace/nombre de la vista
        """
        if request.resolver_match.app_name == 'admin' or request.resolver_match.url_name == 'logout':
            return True
        
        # Resolver la App por el view_name (ej: 'contabilidad:editar_cuenta')
        view_name = request.resolver_match.view_name
        app = cls.objects.filter(
            url=view_name,
            userpermission__is_active=True,
        ).first()

        if app:
            return app

        # Si es una petición AJAX/API y no está mapeada como App independiente, 
        # permitimos que pase o retornamos True según tu regla de negocio
        if request.headers.get('X-App-Request') == "true":
            return True

        return None
