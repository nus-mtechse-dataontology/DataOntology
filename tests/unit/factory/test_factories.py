from unittest.mock import Mock, patch
import pytest

from factory.database_factory import DatabaseFactory

def test_database_factory_create_driver_success():
    factory = DatabaseFactory()
    
    mock_module = Mock()
    mock_class = Mock()
    setattr(mock_module, "SomeDriverClass", mock_class)
    
    with patch("factory.database_factory.im.import_module", return_value=mock_module) as mock_import:
        driver_class = factory.create_driver("some.package", "SomeDriverClass")
        
        mock_import.assert_called_once_with("some.package", "some.package")
        assert driver_class == mock_class

def test_database_factory_create_driver_import_error():
    factory = DatabaseFactory()
    
    with patch("factory.database_factory.im.import_module", side_effect=ImportError("Module not found")):
        with pytest.raises(ImportError):
            factory.create_driver("invalid.package", "SomeDriverClass")

def test_database_factory_create_driver_attribute_error():
    factory = DatabaseFactory()
    
    mock_module = Mock(spec=[]) # No attributes
    with patch("factory.database_factory.im.import_module", return_value=mock_module):
        with pytest.raises(AttributeError):
            factory.create_driver("some.package", "InvalidClass")
