"""add_sample_vacancies

Revision ID: 7ffa784ab042
Revises: a694f7c9e766
Create Date: 2025-08-30 20:00:00.661534

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7ffa784ab042"
down_revision: str | Sequence[str] | None = "a694f7c9e766"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add sample vacancies."""

    # Create sample vacancies data
    vacancies_data = [
        {
            "title": "Senior Python Developer",
            "description": """Мы ищем опытного Python-разработчика для работы в команде разработки высоконагруженного веб-сервиса.

Обязанности:
• Разработка и поддержка API на Python (FastAPI/Django)
• Оптимизация производительности приложений
• Проектирование архитектуры микросервисов
• Код-ревью и менторство младших разработчиков
• Участие в планировании и декомпозиции задач

Требования:
• Опыт разработки на Python от 5 лет
• Глубокие знания Django/FastAPI, SQLAlchemy, PostgreSQL
• Опыт работы с Redis, RabbitMQ/Kafka
• Знание Docker, Kubernetes
• Опыт работы с микросервисной архитектурой
• Понимание принципов SOLID, DRY, KISS

Будет плюсом:
• Опыт работы с облачными сервисами (AWS/GCP)
• Знание Go или Node.js
• Опыт ведения технических интервью""",
            "key_skills": "Python, FastAPI, Django, PostgreSQL, Redis, Docker, Kubernetes, Микросервисы, REST API, Git",
            "employment_type": "FULL_TIME",
            "experience": "MORE_THAN_6",
            "schedule": "REMOTE",
            "salary_from": 250000,
            "salary_to": 400000,
            "salary_currency": "RUR",
            "gross_salary": False,
            "company_name": "TechCorp Solutions",
            "company_description": "Компания-разработчик инновационных решений в области fintech. У нас работает более 500 специалистов, офисы в Москве и Санкт-Петербурге.",
            "area_name": "Москва",
            "metro_stations": "Сокольники, Красносельская",
            "address": "г. Москва, ул. Русаковская, д. 13",
            "professional_roles": "Программист, разработчик",
            "contacts_name": "Анна Петрова",
            "contacts_email": "hr@techcorp.ru",
            "contacts_phone": "+7 (495) 123-45-67",
            "is_archived": False,
            "premium": True,
            "url": "https://techcorp.ru/careers/senior-python",
        },
        {
            "title": "Frontend React Developer",
            "description": """Приглашаем талантливого фронтенд-разработчика для создания современных веб-приложений.

Задачи:
• Разработка пользовательских интерфейсов на React
• Интеграция с REST API
• Оптимизация производительности приложений
• Написание unit-тестов
• Участие в планировании UX/UI решений

Требования:
• Опыт работы с React от 3 лет
• Знание TypeScript, HTML5, CSS3, SASS/SCSS
• Опыт работы с Redux/MobX
• Знание современных инструментов сборки (Webpack, Vite)
• Понимание принципов responsive design
• Опыт работы с Git

Мы предлагаем:
• Интересные задачи и современный стек технологий
• Гибкий график работы
• Медицинское страхование
• Обучение за счет компании
• Дружная команда профессионалов""",
            "key_skills": "React, TypeScript, JavaScript, HTML5, CSS3, SASS, Redux, Webpack, Git, REST API",
            "employment_type": "FULL_TIME",
            "experience": "BETWEEN_3_AND_6",
            "schedule": "FLEXIBLE",
            "salary_from": 150000,
            "salary_to": 250000,
            "salary_currency": "RUR",
            "gross_salary": False,
            "company_name": "Digital Agency Pro",
            "company_description": "Креативное digital-агентство, специализирующееся на разработке веб-приложений и мобильных решений для крупных брендов.",
            "area_name": "Санкт-Петербург",
            "metro_stations": "Технологический институт, Пушкинская",
            "address": "г. Санкт-Петербург, ул. Правды, д. 10",
            "professional_roles": "Программист, разработчик",
            "contacts_name": "Михаил Сидоров",
            "contacts_email": "jobs@digitalagency.ru",
            "contacts_phone": "+7 (812) 987-65-43",
            "is_archived": False,
            "premium": False,
            "url": "https://digitalagency.ru/vacancy/react-dev",
        },
        {
            "title": "DevOps Engineer",
            "description": """Ищем DevOps-инженера для автоматизации процессов CI/CD и управления облачной инфраструктурой.

Основные задачи:
• Проектирование и поддержка CI/CD pipeline
• Управление Kubernetes кластерами
• Мониторинг и логирование приложений
• Автоматизация deployment процессов
• Обеспечение отказоустойчивости сервисов
• Оптимизация затрат на инфраструктуру

Требования:
• Опыт работы DevOps от 4 лет
• Глубокие знания Docker, Kubernetes
• Опыт работы с облачными платформами (AWS/Azure/GCP)
• Знание Terraform, Ansible
• Опыт с Jenkins, GitLab CI/CD
• Знание мониторинга (Prometheus, Grafana, ELK)
• Понимание сетевых технологий

Условия:
• Официальное трудоустройство
• Компенсация обучения и сертификации
• Современное оборудование
• Возможность работы из дома""",
            "key_skills": "Docker, Kubernetes, AWS, Terraform, Ansible, Jenkins, GitLab CI/CD, Prometheus, Grafana, Linux",
            "employment_type": "FULL_TIME",
            "experience": "BETWEEN_3_AND_6",
            "schedule": "REMOTE",
            "salary_from": 200000,
            "salary_to": 350000,
            "salary_currency": "RUR",
            "gross_salary": False,
            "company_name": "CloudTech Systems",
            "company_description": "Системный интегратор, специализирующийся на внедрении облачных решений и автоматизации IT-процессов для корпоративных клиентов.",
            "area_name": "Москва",
            "metro_stations": "Белорусская, Маяковская",
            "address": "г. Москва, Тверская ул., д. 25",
            "professional_roles": "Системный администратор, DevOps",
            "contacts_name": "Елена Васильева",
            "contacts_email": "hr@cloudtech.ru",
            "contacts_phone": "+7 (495) 555-12-34",
            "is_archived": False,
            "premium": True,
            "url": "https://cloudtech.ru/careers/devops",
        },
        {
            "title": "Junior Java Developer",
            "description": """Приглашаем начинающего Java-разработчика для участия в крупных enterprise-проектах.

Обязанности:
• Разработка backend-сервисов на Java
• Написание unit и integration тестов
• Участие в code review
• Изучение и применение лучших практик разработки
• Работа в команде по Agile методологии

Требования:
• Знание Java Core, ООП принципов
• Базовое понимание Spring Framework
• Опыт работы с SQL базами данных
• Знание Git
• Желание развиваться и изучать новые технологии
• Понимание принципов REST API

Мы предлагаем:
• Менторство от senior разработчиков
• Обучающие курсы и конференции
• Карьерный рост
• Стабильную зарплату
• Молодая и амбициозная команда
• Интересные проекты в финтех сфере""",
            "key_skills": "Java, Spring Framework, SQL, Git, REST API, JUnit, Maven, PostgreSQL",
            "employment_type": "FULL_TIME",
            "experience": "BETWEEN_1_AND_3",
            "schedule": "FULL_DAY",
            "salary_from": 80000,
            "salary_to": 120000,
            "salary_currency": "RUR",
            "gross_salary": False,
            "company_name": "FinTech Innovations",
            "company_description": "Быстро развивающийся стартап в области финансовых технологий. Создаем инновационные решения для банков и финансовых институтов.",
            "area_name": "Екатеринбург",
            "metro_stations": "Площадь 1905 года, Динамо",
            "address": "г. Екатеринбург, ул. Ленина, д. 33",
            "professional_roles": "Программист, разработчик",
            "contacts_name": "Дмитрий Козлов",
            "contacts_email": "recruitment@fintech-inn.ru",
            "contacts_phone": "+7 (343) 456-78-90",
            "is_archived": False,
            "premium": False,
            "url": "https://fintech-inn.ru/jobs/java-junior",
        },
        {
            "title": "Product Manager IT",
            "description": """Ищем опытного продуктового менеджера для управления развитием digital-продуктов.

Основные задачи:
• Управление продуктовой стратегией и roadmap
• Анализ потребностей пользователей и рынка
• Координация работы команд разработки
• A/B тестирование и анализ метрик
• Планирование релизов и feature delivery
• Взаимодействие с stakeholders
• Управление product backlog

Требования:
• Опыт работы Product Manager от 4 лет
• Знание методологий Agile/Scrum
• Опыт работы с аналитическими системами
• Понимание UX/UI принципов
• Навыки работы с Jira, Confluence
• Опыт проведения интервью с пользователями
• Аналитическое мышление и data-driven подход

Что мы предлагаем:
• Высокую степень влияния на продукт
• Работу с топ-менеджментом компании
• Современные инструменты и методики
• Конкурентную заработную плату
• Полный соц. пакет и ДМС""",
            "key_skills": "Product Management, Agile, Scrum, Аналитика, UX/UI, Jira, A/B тестирование, User Research",
            "employment_type": "FULL_TIME",
            "experience": "BETWEEN_3_AND_6",
            "schedule": "FLEXIBLE",
            "salary_from": 180000,
            "salary_to": 280000,
            "salary_currency": "RUR",
            "gross_salary": False,
            "company_name": "Marketplace Solutions",
            "company_description": "Один из лидеров российского e-commerce рынка. Развиваем крупнейшую онлайн-платформу с миллионами пользователей.",
            "area_name": "Москва",
            "metro_stations": "Парк культуры, Сокольники",
            "address": "г. Москва, Садовая-Триумфальная ул., д. 4/10",
            "professional_roles": "Менеджер продукта, Product Manager",
            "contacts_name": "Ольга Смирнова",
            "contacts_email": "pm-jobs@marketplace.ru",
            "contacts_phone": "+7 (495) 777-88-99",
            "is_archived": False,
            "premium": True,
            "url": "https://marketplace.ru/career/product-manager",
        },
    ]

    # Insert vacancies using raw SQL with proper enum casting
    for vacancy_data in vacancies_data:
        op.execute(f"""
            INSERT INTO vacancy (
                title, description, key_skills, employment_type, experience, 
                schedule, salary_from, salary_to, salary_currency, gross_salary,
                company_name, company_description, area_name, metro_stations, address,
                professional_roles, contacts_name, contacts_email, contacts_phone,
                is_archived, premium, published_at, url, created_at, updated_at
            ) VALUES (
                '{vacancy_data["title"]}',
                '{vacancy_data["description"].replace("'", "''")}',
                '{vacancy_data["key_skills"]}',
                '{vacancy_data["employment_type"]}'::employmenttype,
                '{vacancy_data["experience"]}'::experience,
                '{vacancy_data["schedule"]}'::schedule,
                {vacancy_data["salary_from"]},
                {vacancy_data["salary_to"]},
                '{vacancy_data["salary_currency"]}',
                {vacancy_data["gross_salary"]},
                '{vacancy_data["company_name"]}',
                '{vacancy_data["company_description"].replace("'", "''")}',
                '{vacancy_data["area_name"]}',
                '{vacancy_data["metro_stations"]}',
                '{vacancy_data["address"]}',
                '{vacancy_data["professional_roles"]}',
                '{vacancy_data["contacts_name"]}',
                '{vacancy_data["contacts_email"]}',
                '{vacancy_data["contacts_phone"]}',
                {vacancy_data["is_archived"]},
                {vacancy_data["premium"]},
                NOW(),
                '{vacancy_data["url"]}',
                NOW(),
                NOW()
            )
        """)


def downgrade() -> None:
    """Remove sample vacancies."""
    # Remove the sample vacancies by their unique titles
    sample_titles = [
        "Senior Python Developer",
        "Frontend React Developer",
        "DevOps Engineer",
        "Junior Java Developer",
        "Product Manager IT",
    ]

    for title in sample_titles:
        op.execute(f"DELETE FROM vacancy WHERE title = '{title}'")
