from django.test import TestCase
from django.core.management import call_command
from unittest.mock import patch, MagicMock
from apps.catalogo.models import Department, Province, District
from django.contrib.gis.geos import Polygon
from apps.inversiones.models import Project

class ImportDistritosCommandTest(TestCase):
    
    def setUp(self):
        # Create a dummy polygon to use as mock geometry
        self.dummy_polygon = Polygon(((0.0, 0.0), (0.0, 1.0), (1.0, 1.0), (1.0, 0.0), (0.0, 0.0)))
        
    @patch('apps.ingestion.management.commands.import_distritos.DataSource')
    @patch('apps.ingestion.management.commands.import_distritos.os.path.exists')
    def test_import_distritos_idempotency_and_dry_run(self, mock_exists, mock_datasource):
        # Setup mocks
        mock_exists.return_value = True
        
        # Mock feature
        mock_feature = MagicMock()
        mock_feature.get.side_effect = lambda key: {
            'CODDEP': '15',
            'DEPARTAMEN': 'LIMA',
            'CODPROV': '01',
            'PROVINCIA': 'LIMA',
            'UBIGEO': '150101',
            'DISTRITO': 'LIMA'
        }.get(key)
        
        mock_geom = MagicMock()
        mock_geom.geos = self.dummy_polygon
        mock_feature.geom = mock_geom
        
        # Mock layer (iterable of features)
        mock_layer = MagicMock()
        mock_layer.__iter__.side_effect = lambda: iter([mock_feature])
        mock_layer.srs = MagicMock(srid=4326)
        mock_layer.name = 'MOCK_LAYER'
        
        # Mock datasource indexing to return layer
        mock_ds_instance = MagicMock()
        mock_ds_instance.__getitem__.return_value = mock_layer
        mock_datasource.return_value = mock_ds_instance

        # 1. Test Dry Run
        with patch('sys.stdout'):  # suppress output
            call_command('import_distritos', file='dummy.shp', source_version='TEST', dry_run=True)
            
        # Ensure nothing was saved
        self.assertEqual(Department.objects.count(), 0)
        self.assertEqual(Province.objects.count(), 0)
        self.assertEqual(District.objects.count(), 0)
        
        # 2. Test First Real Run (Populate)
        with patch('sys.stdout'):
            call_command('import_distritos', file='dummy.shp', source_version='TEST')
            
        # Verify created
        self.assertEqual(Department.objects.count(), 1)
        self.assertEqual(Province.objects.count(), 1)
        self.assertEqual(District.objects.count(), 1)
        
        dist = District.objects.get(ubigeo='150101')
        self.assertEqual(dist.name, 'LIMA')
        self.assertEqual(dist.province.code, '1501')
        self.assertEqual(dist.province.department.code, '15')
        
        # 3. Test Second Real Run (Idempotency)
        with patch('sys.stdout'):
            call_command('import_distritos', file='dummy.shp', source_version='TEST')
            
        # Verify count is the same
        self.assertEqual(Department.objects.count(), 1)
        self.assertEqual(Province.objects.count(), 1)
        self.assertEqual(District.objects.count(), 1)

from apps.ingestion.management.commands.import_inversiones import Command

class ImportInversionesCommandTest(TestCase):
    def setUp(self):
        dummy_poly = Polygon(((0.0, 0.0), (0.0, 1.0), (1.0, 1.0), (1.0, 0.0), (0.0, 0.0)))
        from django.contrib.gis.geos import MultiPolygon
        self.dummy_poly = MultiPolygon(dummy_poly)
        self.dep = Department.objects.create(code='21', name='Puno', slug='puno', geometry=self.dummy_poly)
        self.prov = Province.objects.create(code='2111', name='San Roman', department=self.dep, geometry=self.dummy_poly)
        self.dist = District.objects.create(ubigeo='211101', name='Juliaca', province=self.prov, geometry=self.dummy_poly)
        
    def test_parse_location_and_cui(self):
        cmd = Command()
        
        text = "MEJORAMIENTO DEL SERVICIO DE AGUA EN EL DISTRITO DE JULIACA - PROVINCIA DE SAN ROMAN - DEPARTAMENTO DE PUNO"
        dist, prov = cmd.parse_location(text)
        self.assertEqual(dist, "JULIACA")
        self.assertEqual(prov, "SAN ROMAN")
        
        found_dist = cmd.find_district("JULIACA", "SAN ROMAN")
        self.assertIsNotNone(found_dist)
        self.assertEqual(found_dist.ubigeo, '211101')
        
    @patch('apps.ingestion.management.commands.import_inversiones.pd.read_excel')
    @patch('apps.ingestion.management.commands.import_inversiones.glob.glob')
    def test_import_command(self, mock_glob, mock_read_excel):
        mock_glob.return_value = ['dummy.xlsx']
        
        import pandas as pd
        mock_df = pd.DataFrame([{
            'Código Único': '2402140.0',
            'Nombre de inversión': 'MEJORAMIENTO EN EL DISTRITO DE JULIACA - PROVINCIA DE SAN ROMAN',
            'Función': 'SANEAMIENTO',
            'Costo actualizado (S/)': 1000.50
        }])
        mock_read_excel.return_value = mock_df
        
        with patch('sys.stdout'):
            call_command('import_inversiones')
        
        proj = Project.objects.first()
        self.assertIsNotNone(proj)
        self.assertEqual(proj.cui, '2402140')
        self.assertEqual(proj.district.ubigeo, '211101')
        self.assertEqual(proj.cost, 1000.50)
