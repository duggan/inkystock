import os
from configparser import ConfigParser
from typing import List, Optional, Union
from pydantic import BaseModel, validator, HttpUrl
from inky.auto import auto


class ConfigurationException(ValueError):
    """Configuration Exception"""


class MainConfig(BaseModel):
    currency = "EUR"
    database = "sqlite:////tmp/inkystock.db"
    stock: str = ""
    crypto: str = "BTC"
    provider: str = "CoinGecko"
    display_width_pixels: Union[int,str] = 'auto'
    display_height_pixels: Union[int,str] = 'auto'
    display_diagonal_inches: float = 2.13
    rotate_display: int = 0
    loglevel: str = "INFO"
    color: str = 'auto'

    @validator('display_width_pixels', pre=True, always=True)
    def auto_display_width(cls, v):
        if not v or v == 'auto':
            display = auto()
            return display.resolution[0]
        return v

    @validator('display_height_pixels', pre=True, always=True)
    def auto_display_height(cls, v):
        if not v or v == 'auto':
            display = auto()
            return display.resolution[1]
        return v

    @validator('color', pre=True, always=True)
    def auto_color(cls, v):
        if not v or v == 'auto':
            display = auto()
            return display.colour
        return v

    @validator('currency')
    def currency_is_upper(cls, v):
        if not v.isupper():
            raise ConfigurationException("must be uppercase")
        return v

    @validator('stock')
    def only_stock_set(cls, v, values, **kwargs):
        if len(v) and len(values.get('crypto', "")):
            raise ConfigurationException('One of *either* stock or crypto must be specified')
        return v

    @validator('crypto')
    def only_crypto_set(cls, v, values, **kwargs):
        if len(v) and len(values.get('stock', "")):
            raise ConfigurationException("One of *either* stock or crypto must be specified")
        return v

    @validator('loglevel')
    def valid_loglevel(cls, v):
        loglevels = ['NOTSET', 'CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG']
        if not v.isupper():
            raise ConfigurationException("must be uppercase")
        if v not in loglevels:
            raise ConfigurationException(f"loglevel must be one of {loglevels}")
        return v


class FontsConfig(BaseModel):
    ticker: str = "./resources/fonts/04B_03__.TTF"
    ticker_size: int = 8
    symbol: str = "./resources/fonts/04B_21__.TTF"
    symbol_size: int = 10
    statusbar: str = "./resources/fonts/CozetteVector.ttf"
    statusbar_size: int = 12
    headline: str = "./resources/fonts/04B_30__.TTF"
    headline_size: int = 30
    chart: str = "./resources/fonts/04B_03__.TTF"
    chart_size: float = 5.2


class MascotConfig(BaseModel):
    increasing: str = "./resources/pixelcat/pixelcat_cool.png"
    decreasing: str = "./resources/pixelcat/pixelcat_worried.png"
    static: str = "./resources/pixelcat/pixelcat_sleeping.png"


class IEXConfig(BaseModel):
    token: str
    endpoint: HttpUrl = "https://cloud.iexapis.com/stable"

    @validator('token', 'endpoint')
    def strip_quotes(cls, v):
        if v and "'" in v:
            return v.strip("'")
        if v and '"' in v:
            return v.strip('"')
        return v

class CoinGecko(BaseModel):
    api_key: str

    @validator('api_key')
    def strip_quotes(cls, v):
        if v and "'" in v:
            return v.strip("'")
        if v and '"' in v:
            return v.strip('"')
        return v


class OutputConfig(BaseModel):
    screen: str = "inky"
    local: str = "./data/out.png"


class Config:

    def __init__(self, env_vars: Optional[List] = None, path: str = 'config.ini'):
        """
        Read configuration file and set map to Pydantic models.
        :param path: path to the configuration file
        :param: env: environment dictionary
        :return: a Config object
        :rtype: Config
        """
        # Populate the config with environment variables
        env = {}
        if env_vars is None:
            env_vars = []
        for env_var in env_vars:
            if os.getenv(env_var):
                env[env_var] = str(os.getenv(env_var))

        self.__config = ConfigParser(env)
        self.__config.read(path)

        self.main = MainConfig(**self.__config['Main'])
        self.outputs = OutputConfig()
        if self.__config.has_section('Outputs'):
            self.outputs = OutputConfig(**self.__config['Outputs'])
        self.fonts = FontsConfig(**self.__config['Fonts'])
        self.mascot = MascotConfig(**self.__config['Mascot'])

        # IEXCloud provider configuration
        self.iex = IEXConfig(token="")
        if self.main.provider == 'IEX':
            self.iex = IEXConfig(**self.__config['IEX'])

        # CoinGecko provider configuration
        self.coingecko = CoinGecko(api_key="")
        if self.main.provider == 'CoinGecko':
            self.coingecko = CoinGecko(**self.__config['CoinGecko'])
