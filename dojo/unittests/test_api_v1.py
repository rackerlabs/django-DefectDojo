import random
from unittest import skip

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from tastypie.models import ApiKey
from tastypie.test import ResourceTestCaseMixin

from dojo.models import Product, Engagement, Product_Type


@override_settings(LEGACY_API_V1_ENABLE=True)
class ApiBasicOperationsTest(ResourceTestCaseMixin, TestCase):
    def setUp(self):
        super(ApiBasicOperationsTest, self).setUp()
        self.username = "test_user"
        self.password = "p4ss"
        self.user = User.objects.create_user(
            self.username,
            "user@mail.com",
            self.password,
            is_active=True,
            is_staff=True,
            is_superuser=True,
        )
        self.api_key = ApiKey.objects.create(user=self.user)

        self.prod_type = Product_Type.objects.create(name="WebApp")

    def get_credentials(self):
        return self.create_apikey(self.username, self.user.api_key.key)

    def prepare_a_product(self):
        self.product_name = "Product %s" % str(random.randint(0, 999))
        description = "A precise product description"
        return Product.objects.create(
            name=self.product_name, description=description, prod_type=self.prod_type
        )

    def test_unauthenticated_request(self):
        """
        An unauthenticated request should return an HTTP Unauthorized (401)
        code.
        """
        r = self.api_client.get("/api/v1/products/")
        self.assertHttpUnauthorized(r)

    def test_list_products(self):
        p = self.prepare_a_product()
        r = self.api_client.get(
            "/api/v1/products/?name=%s" % self.product_name,
            authentication=self.get_credentials(),
        )
        self.assertValidJSONResponse(r)
        data = self.deserialize(r)
        self.assertEqual(1, len(data["objects"]))
        self.assertEqual(
            "/api/v1/products/%s/" % p.id, data["objects"][0]["resource_uri"]
        )
        self.assertEqual(p.id, data["objects"][0]["id"])

    def test_get_product_detail(self):
        p = self.prepare_a_product()
        r = self.api_client.get(
            "/api/v1/products/%s/" % p.id, authentication=self.get_credentials()
        )
        self.assertValidJSONResponse(r)
        data = self.deserialize(r)
        self.assertEqual(p.id, data["id"])

    def test_create_product(self):
        p_data = {
            "name": "Fantastic Product",
            "description": "Our most recent fantastic product",
            "prod_type": self.prod_type.id,
        }
        r = self.api_client.post(
            "/api/v1/products/", data=p_data, authentication=self.get_credentials()
        )
        self.assertHttpCreated(r)
        created_uri = r["Location"]
        obj_id = created_uri.split("/")[-2]
        p = Product.objects.get(id=obj_id)
        self.assertEqual("Fantastic Product", p.name)

    # @skip("TODO: Test for product updating")
    def test_update_product(self):
        new_p_data = {
            "name": "Wonderful Product",
            "description": "This is an awesome updated product",
            "prod_type": self.prod_type.id,
        }
        p = self.prepare_a_product()
        self.api_client.put(
            "/api/v1/products/%s/" % p.id,
            data=new_p_data,
            authentication=self.get_credentials(),
        )
        r = self.api_client.get(
            "/api/v1/products/%s/" % p.id, authentication=self.get_credentials()
        )
        self.assertValidJSONResponse(r)
        data = self.deserialize(r)
        self.assertEqual("Wonderful Product", data["name"])

    @skip("TODO: Test for product deletion")
    def test_delete_product(self):
        pass

    def test_create_engagement(self):
        """
        Test for engagement creation, because it takes at least one reference
        to another model.
        """
        p = self.prepare_a_product()
        engagement_name = "Test Create Engagement"
        product_uri = "/api/v1/products/%s/" % str(p.id)
        user_uri = "/api/v1/users/%s/" % str(self.user.id)
        e_data = {
            "name": engagement_name,
            "product": product_uri,
            "lead": user_uri,
            "status": "In Progress",
            "target_start": "2018-01-01",
            "target_end": "2025-12-31",
        }
        r = self.api_client.post(
            "/api/v1/engagements/", data=e_data, authentication=self.get_credentials()
        )
        self.assertHttpCreated(r)

        # Verify the object's creation
        e = Engagement.objects.get(name=engagement_name)
        self.assertEqual("2018-01-01", e.target_start.strftime("%Y-%m-%d"))
        self.assertEqual("2025-12-31", e.target_end.strftime("%Y-%m-%d"))

    def test_inclomplete_creation_request(self):
        """
        Demonstrate what happens, if not all required fields are provided in a
        creation request.
        """
        p = self.prepare_a_product()
        product_uri = "/api/v1/products/%s/" % str(p.id)
        user_uri = "/api/v1/users/%s/" % str(self.user.id)
        e_data = {
            "product": product_uri,
            "lead": user_uri,
        }
        r = self.api_client.post(
            "/api/v1/engagements/", data=e_data, authentication=self.get_credentials()
        )
        self.assertHttpBadRequest(r)
        data = self.deserialize(r)
        self.assertEqual(
            data,
            {
                "engagements": {
                    "status": ["This field is required."],
                    "target_end": ["This field is required."],
                    "target_start": ["This field is required."],
                }
            },
        )


@override_settings(LEGACY_API_V1_ENABLE=False)
class ApiV1Disabled(ResourceTestCaseMixin, TestCase):
    def setUp(self):
        super(ApiV1Disabled, self).setUp()
        self.username = "test_user"
        self.password = "p4ss"
        self.user = User.objects.create_user(
            self.username,
            "user@mail.com",
            self.password,
            is_active=True,
            is_staff=True,
            is_superuser=True,
        )
        self.api_key = ApiKey.objects.create(user=self.user)

        self.prod_type = Product_Type.objects.create(name="WebApp")

    def get_credentials(self):
        return self.create_apikey(self.username, self.user.api_key.key)

    def test_api_v1_disabled(self):
        r = self.api_client.get(
            "/api/v1/products/", authentication=self.get_credentials()
        )

        self.assertHttpBadRequest(r)
        data = self.deserialize(r)
        print(data)
        self.assertTrue("666" in str(data))
