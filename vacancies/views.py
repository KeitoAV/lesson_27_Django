import json

from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Count, Avg
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import DetailView, ListView, CreateView, UpdateView, DeleteView
from poetry.json import ValidationError

from lesson_27_django import settings
from vacancies.models import Vacancy, Skill


def hello(request):
    return HttpResponse("Hello world")


# @csrf_exempt # декоратор для функций, откл проверку токена
# @method_decorator(csrf_exempt, name="dispatch")  # декоратор для классов, откл проверку токена
class VacancyListView(ListView):
    model = Vacancy

    def get(self, request, *args, **kwargs):
        super().get(request, *args, **kwargs)

        search_text = request.GET.get("text", None)
        if search_text:
            self.object_list = self.object_list.filter(text=search_text)

        self.object_list = self.object_list.select_related("user").prefetch_related("skills").order_by("text")  # сортировка

        """
        Пагинация:
        1 - 0:10
        2 - 10:20
        3 - 20:30
        """

        # total = self.object_list.count()
        # page_number = int(request.GET.get("page", 1))
        # offset = (page_number-1) * settings.TOTAL_ON_PAGE
        # if offset < total:
        #     self.object_list = self.object_list[offset:offset+settings.TOTAL_ON_PAGE]
        # else:
        #     self.object_list = self.object_list[offset:offset + total]

        paginator = Paginator(self.object_list, settings.TOTAL_ON_PAGE)
        page_number = request.GET.get("page")
        page_obj = paginator.get_page(page_number)

        vacancies = []
        for vacancy in page_obj:
            vacancies.append({
                "id": vacancy.id,
                "slug": vacancy.slug,
                "text": vacancy.text,
                "status": vacancy.status,
                "created": vacancy.created,
                "username": vacancy.user.username,
                "skills": list(map(str, vacancy.skills.all())),

            })

        response = {
            "item": vacancies,
            "num_page": paginator.num_pages,
            "total": paginator.count
        }

        return JsonResponse(response, safe=False, json_dumps_params={"ensure_ascii": False})


class VacancyDetailView(DetailView):
    model = Vacancy

    def get(self, request, *args, **kwargs):
        vacancy = self.get_object()

        return JsonResponse({
            "id": vacancy.id,
            "text": vacancy.text,
            "user": vacancy.user_id,
            "slug": vacancy.slug,
            "status": vacancy.status,
            "created": vacancy.created,
            "skills": list(map(str, vacancy.skills.all())),

        }, safe=False, json_dumps_params={"ensure_ascii": False})


@method_decorator(csrf_exempt, name="dispatch")
class VacancyCreateView(CreateView):
    model = Vacancy
    fields = ["user", "slug", "text", "status", "created", "skills"]

    def post(self, request, *args, **kwargs):
        vacancy_data = json.loads(request.body)

        vacancy = Vacancy.objects.create(
            user_id=vacancy_data["user_id"],
            slug=vacancy_data["slug"],
            text=vacancy_data["text"],
            status=vacancy_data["status"]

        )

        vacancy.user = get_object_or_404(User, pk=vacancy_data["user_id"])  # обработка ошибок - 404

        for skill in vacancy_data["skills"]:
            # try:
            #     skill_obj = Skill.objects.get(name=skill)
            # except Skill.DoesNotExist:
            #     return JsonResponse({"error": "Skill not found"}, status=404)
            skill_obj, created = Skill.objects.get_or_create(
                name=skill,
                defaults={
                    "is_active": True
                }
            )
            vacancy.skills.add(skill_obj)

        vacancy.save()

        return JsonResponse({
            "id": vacancy.id,
            "text": vacancy.text,
            "user": vacancy.user_id,
            "slug": vacancy.slug,
            "status": vacancy.status,
            "created": vacancy.created,
            "skills": list(map(str, vacancy.skills.all())),
        },
            safe=False, json_dumps_params={"ensure_ascii": False})


@method_decorator(csrf_exempt, name="dispatch")
class VacancyUpdateView(UpdateView):
    model = Vacancy
    fields = ["slug", "text", "status", "skills"]

    def patch(self, request, *args, **kwargs):
        super().post(request, *args, **kwargs)

        vacancy_data = json.loads(request.body)

        self.object.slug = vacancy_data["slug"]
        self.object.text = vacancy_data["text"]
        self.object.status = vacancy_data["status"]

        for skill in vacancy_data["skills"]:
            try:
                skill_obj = Skill.objects.get(name=skill)
            except Skill.DoesNotExist:
                return JsonResponse({"error": "Skill not found"}, status=404)
            self.object.skills.add(skill_obj)

        self.object.save()

        return JsonResponse({
            "id": self.object.id,
            "slug": self.object.slug,
            "text": self.object.text,
            "status": self.object.status,
            "created": self.object.created,
            "user": self.object.user_id,
            "skills": list(self.object.skills.all().values_list("name", flat=True)),
        },
            safe=False, json_dumps_params={"ensure_ascii": False})


@method_decorator(csrf_exempt, name='dispatch')
class VacancyDeleteView(DeleteView):
    model = Vacancy
    success_url = "/"

    def delete(self, request, *args, **kwargs):
        super().delete(request, *args, **kwargs)

        return JsonResponse({"status": "ok"}, status=200)


class UserVacancyDetailView(View):  # группировки
    def get(self, request):
        users_qs = User.objects.annotate(vacancies=Count('vacancy'))

        paginator = Paginator(users_qs, settings.TOTAL_ON_PAGE)
        page_number = request.GET.get("page")
        page_obj = paginator.get_page(page_number)

        users = []
        for user in page_obj:
            users.append({
                "id": user.id,
                "name": user.username,
                "vacancies": user.vacancies,

            })

        response = {
            "item": users,
            "num_page": paginator.num_pages,
            "total": paginator.count,
            "avg": users_qs.aggregate(avg=Avg("vacancies"))["avg"],  # среднее по колонке вакансии
        }

        return JsonResponse(response, safe=False, json_dumps_params={"ensure_ascii": False})

