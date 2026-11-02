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
        filtrando mediante UserPermission activo (evitando importaciones circulares).
        """
        # Importación local para evitar importaciones circulares al arrancar Django
        from core.models.user import UserPermission

        # 1. Obtenemos los IDs de las aplicaciones permitidas para este usuario y rol
        # donde UserPermission esté activo (is_active=True)
        allowed_app_ids = UserPermission.objects.filter(
            user=user,
            role=session_role,
            is_active=True  # Campo heredado de BaseModel
        ).values_list('app_id', flat=True).distinct()

        # 2. Creamos el queryset base de aplicaciones permitidas
        allowed_apps_queryset = cls.objects.filter(
            id__in=allowed_app_ids
        )

        # 3. Prefetch de NIETAS
        prefetch_granddaughters = models.Prefetch(
            'sub_apps',
            queryset=allowed_apps_queryset.order_by('order'),
            to_attr='allowed_daughters'
        )

        # 4. Prefetch de HIJAS con sus respectivas nietas
        prefetch_daughters = models.Prefetch(
            'sub_apps',
            queryset=allowed_apps_queryset.prefetch_related(prefetch_granddaughters).order_by('order'),
            to_attr='allowed_daughters'
        )

        # 5. Traemos todas las aplicaciones PADRE permitidas
        parents = cls.objects.filter(
            id__in=allowed_app_ids,
            father_app__isnull=True
        ).prefetch_related(
            prefetch_daughters
        ).distinct().order_by('order')

        # 6. Filtrado jerárquico en memoria
        visible_parents = []

        for father in parents:
            visible_daughters = []
            for daughter in getattr(father, 'allowed_daughters', []):
                has_db_granddaughters = daughter.sub_apps.exists()

                if has_db_granddaughters:
                    if getattr(daughter, 'allowed_daughters', []):
                        visible_daughters.append(daughter)
                else:
                    visible_daughters.append(daughter)

            father.allowed_daughters = visible_daughters

            has_db_daughters = father.sub_apps.exists()

            if has_db_daughters:
                if visible_daughters:
                    visible_parents.append(father)
            else:
                visible_parents.append(father)

        return visible_parents

    @classmethod
    def get_app_by_request(cls, request):
        """
        Identifica la App actual comparando el namespace/nombre de la vista
        y validando permisos activos en UserPermission.
        """
        if not hasattr(request, 'resolver_match') or not request.resolver_match:
            return None

        if request.resolver_match.app_name == 'admin' or request.resolver_match.url_name == 'logout':
            return True
        
        view_name = request.resolver_match.view_name
        
        if hasattr(request, 'user') and request.user.is_authenticated:
            # Importación local para evitar ciclos
            from core.models.user import UserPermission
            
            session_role = request.session.get('session_role') if hasattr(request, 'session') else None
            
            up_filters = {
                'user': request.user,
                'app__url': view_name,
                'is_active': True,
            }
            if session_role:
                up_filters['role'] = session_role

            allowed_app_ids = UserPermission.objects.filter(**up_filters).values_list('app_id', flat=True).distinct()
            app = cls.objects.filter(id__in=allowed_app_ids, url=view_name).first()
        else:
            app = cls.objects.filter(url=view_name).first()

        if app:
            return app

        # Si es una petición AJAX/API y no está mapeada como App independiente, 
        # permitimos que pase o retornamos True según tu regla de negocio
        if request.headers.get('X-App-Request') == "true":
            return True

        return None