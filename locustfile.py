from locust import HttpUser, task, between

class DjangoAdminUser(HttpUser):
    endpoints = [
    "/sites/<site>/type/",
    ]

    def on_start(self):
        self.client.get("/admin/login/")
        self.login()

    def login(self):
        csrf_token = self.client.cookies['csrftoken']
        response = self.client.post(
            "/admin/login/",
            {
                "username": "<your local django admin username>",
                "password": "<your local django admin password>",
                "csrfmiddlewaretoken": csrf_token,
            },
            headers={"Referer": "/admin/login/"},
        )
        if response.status_code == 200:
            self.navigate_to_endpoints()
    @task
    def navigate_to_endpoints(self):
        for endpoint in self.endpoints:
            self.client.get(endpoint)