from sqladmin import Admin, ModelView, BaseView, expose
from starlette.responses import HTMLResponse
from backend.scoring_engine.models_platform import User, Feis, Competition, Dancer, Entry
import os

# Get the path to templates directory relative to this file
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")

# --- Standard Model Views ---
class UserAdmin(ModelView, model=User):
    column_list = [User.name, User.email, User.role]
    column_searchable_list = [User.name, User.email]
    column_sortable_list = [User.name, User.email, User.role]

class FeisAdmin(ModelView, model=Feis):
    column_list = [Feis.name, Feis.date, Feis.location]
    column_searchable_list = [Feis.name, Feis.location]
    column_sortable_list = [Feis.name, Feis.date]

class CompetitionAdmin(ModelView, model=Competition):
    column_list = [Competition.name, Competition.level, Competition.min_age, Competition.max_age, Competition.gender]
    column_searchable_list = [Competition.name]
    column_sortable_list = [Competition.name, Competition.level, Competition.min_age]

class DancerAdmin(ModelView, model=Dancer):
    column_list = [Dancer.name, Dancer.dob, Dancer.current_level, Dancer.gender]
    column_searchable_list = [Dancer.name]
    column_sortable_list = [Dancer.name, Dancer.dob, Dancer.current_level]

class EntryAdmin(ModelView, model=Entry):
    column_list = [Entry.dancer_id, Entry.competition_id, Entry.paid, Entry.competitor_number]
    column_sortable_list = [Entry.paid]

# --- Custom Views (Placeholder pages linking to Vue frontend) ---

class SyllabusGeneratorView(BaseView):
    name = "Syllabus Generator"
    icon = "fa-solid fa-wand-magic-sparkles"

    @expose("/syllabus", methods=["GET"])
    async def syllabus_page(self, request):
        # Return a simple HTML page that redirects to the Vue frontend
        html_content = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Syllabus Generator - Open Feis</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        </head>
        <body class="bg-light">
            <div class="container py-5">
                <div class="card shadow">
                    <div class="card-header bg-primary text-white">
                        <h3 class="mb-0"><i class="fa-solid fa-wand-magic-sparkles me-2"></i>Syllabus Generator</h3>
                    </div>
                    <div class="card-body">
                        <p class="lead">Auto-generate competitions based on your feis configuration.</p>
                        <p>The full Syllabus Generator is available in the Vue.js frontend.</p>
                        <ul class="list-group list-group-flush mb-3">
                            <li class="list-group-item">Age Groups (U8, U10, U12, etc.)</li>
                            <li class="list-group-item">Gender (Boys, Girls)</li>
                            <li class="list-group-item">Levels (Beginner, Novice, Prizewinner, Championship)</li>
                            <li class="list-group-item">Dances (Reel, Jig, Slip Jig, Hornpipe, Treble Jig)</li>
                        </ul>
                        <a href="http://localhost:5173/" class="btn btn-primary" target="_blank">Open Frontend Generator</a>
                        <a href="/admin" class="btn btn-secondary ms-2">Back to Admin</a>
                    </div>
                </div>
            </div>
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        </body>
        </html>
        """
        return HTMLResponse(content=html_content)

class SchedulerView(BaseView):
    name = "Scheduling Matrix"
    icon = "fa-solid fa-calendar-days"
    
    @expose("/schedule", methods=["GET"])
    async def schedule_page(self, request):
        # Return a simple HTML page that redirects to the Vue frontend
        html_content = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Scheduling Matrix - Open Feis</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        </head>
        <body class="bg-light">
            <div class="container py-5">
                <div class="card shadow">
                    <div class="card-header bg-success text-white">
                        <h3 class="mb-0"><i class="fa-solid fa-calendar-days me-2"></i>Scheduling Matrix</h3>
                    </div>
                    <div class="card-body">
                        <p class="lead">Drag-and-drop stage assignment and load balancing.</p>
                        <p>The full Scheduler is available in the Vue.js frontend.</p>
                        <ul class="list-group list-group-flush mb-3">
                            <li class="list-group-item">Assign competitions to stages</li>
                            <li class="list-group-item">Calculate estimated duration per stage</li>
                            <li class="list-group-item">Identify scheduling conflicts</li>
                            <li class="list-group-item">Load balancing warnings</li>
                        </ul>
                        <a href="http://localhost:5173/" class="btn btn-success" target="_blank">Open Frontend Scheduler</a>
                        <a href="/admin" class="btn btn-secondary ms-2">Back to Admin</a>
                    </div>
                </div>
            </div>
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        </body>
        </html>
        """
        return HTMLResponse(content=html_content)

def setup_admin(app, engine):
    admin = Admin(app, engine, title="Open Feis Admin")
    
    # Register Model Views
    admin.add_view(UserAdmin)
    admin.add_view(FeisAdmin)
    admin.add_view(CompetitionAdmin)
    admin.add_view(DancerAdmin)
    admin.add_view(EntryAdmin)
    
    # Register Custom Views
    admin.add_view(SyllabusGeneratorView)
    admin.add_view(SchedulerView)
    
    return admin
