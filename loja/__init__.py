"""Sistema de gestão para loja de material de construção."""
VERSAO = "1.0.0"

from .sistema import Loja
from .valores import LojaError, NaoEncontrado

__all__ = ["Loja", "LojaError", "NaoEncontrado"]
