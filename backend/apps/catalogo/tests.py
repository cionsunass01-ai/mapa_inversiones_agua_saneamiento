from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.gis.geos import MultiPolygon, Polygon
from apps.catalogo.models import Department, Province, District

class CatalogoAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        dummy_poly = MultiPolygon(Polygon(((0, 0), (0, 1), (1, 1), (1, 0), (0, 0))))
        
        self.dep1 = Department.objects.create(code='01', name='Amazonas', slug='amazonas', geometry=dummy_poly)
        self.dep2 = Department.objects.create(code='15', name='Lima', slug='lima', geometry=dummy_poly)
        
        self.prov1 = Province.objects.create(code='0101', name='Chachapoyas', department=self.dep1, geometry=dummy_poly)
        self.prov2 = Province.objects.create(code='1501', name='Lima', department=self.dep2, geometry=dummy_poly)
        
        self.dist1 = District.objects.create(ubigeo='010101', name='Chachapoyas', province=self.prov1, geometry=dummy_poly)
        self.dist2 = District.objects.create(ubigeo='150101', name='Lima', province=self.prov2, geometry=dummy_poly)
        
        for i in range(2, 105):
            District.objects.create(
                ubigeo=f'{i:06d}', 
                name=f'District {i}', 
                province=self.prov2, 
                geometry=dummy_poly
            )

    def test_department_list(self):
        response = self.client.get(reverse('department-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check GeoJSON structure
        self.assertEqual(response.data['type'], 'FeatureCollection')
        self.assertEqual(len(response.data['features']), 2)
        
    def test_department_filter(self):
        response = self.client.get(reverse('department-list'), {'code': '15'})
        self.assertEqual(len(response.data['features']), 1)
        self.assertEqual(response.data['features'][0]['properties']['code'], '15')

    def test_province_filter_by_department(self):
        response = self.client.get(reverse('province-list'), {'department': self.dep2.id})
        self.assertEqual(len(response.data['features']), 1)
        self.assertEqual(response.data['features'][0]['properties']['code'], '1501')

    def test_district_filter_by_province(self):
        response = self.client.get(reverse('district-list'), {'province': self.prov1.id})
        self.assertEqual(len(response.data['features']), 1)
        self.assertEqual(response.data['features'][0]['id'], '010101')

    def test_district_pagination(self):
        # We created 1 + 1 + 103 = 105 districts. Page size is 100.
        response = self.client.get(reverse('district-list'))
        self.assertEqual(len(response.data['features']), 100)
        self.assertIsNotNone(response.data.get('next'))
        
        # Go to page 2
        response2 = self.client.get(response.data['next'])
        self.assertEqual(len(response2.data['features']), 5)
        self.assertIsNone(response2.data.get('next'))
