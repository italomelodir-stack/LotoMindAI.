"""Cópias de segurança automáticas do banco de dados.

Cada backup é conferido (integridade do SQLite) antes de ser aceito. Ficam guardados:
todos os dos últimos 7 dias, um por dia até 90 dias, e sempre pelo menos os 10 mais recentes.
"""
import datetime
import json
import os
import re
import shutil
import threading
import traceback
from pathlib import Path

from .valores import LojaError

PADRAO = re.compile(r"^loja-(\d{4}-\d{2}-\d{2})-(\d{6})(?:-\d+)?\.db$")


class Backups:
    def __init__(self, loja, pasta, agora=datetime.datetime.now):
        self.loja = loja
        self.pasta = Path(pasta)
        self.agora = agora
        self._lock = threading.Lock()
        self._parar = threading.Event()

    # ------------------------------------------------------------- arquivos
    def _arquivos(self, pasta):
        pasta = Path(pasta)
        if not pasta.is_dir():
            return []
        return sorted((p for p in pasta.iterdir() if PADRAO.match(p.name)), key=lambda p: p.name, reverse=True)

    def listar(self):
        lista = []
        for p in self._arquivos(self.pasta):
            m = PADRAO.match(p.name)
            h = m.group(2)
            lista.append({"nome": p.name, "data": f"{m.group(1)} {h[:2]}:{h[2:4]}:{h[4:]}", "tamanho": p.stat().st_size})
        return lista

    def limpar(self, pasta):
        hoje = self.agora().date()
        guardar, dias_vistos = set(), set()
        arquivos = self._arquivos(pasta)
        for i, p in enumerate(arquivos):                      # do mais novo para o mais antigo
            dia = datetime.date.fromisoformat(PADRAO.match(p.name).group(1))
            idade = (hoje - dia).days
            if i < 10 or idade <= 7 or (idade <= 90 and dia not in dias_vistos):
                guardar.add(p)
            dias_vistos.add(dia)
        for p in arquivos:
            if p not in guardar:
                try:
                    p.unlink()
                except OSError:
                    pass

    # --------------------------------------------------------------- backup
    def fazer(self, motivo="manual"):
        with self._lock:
            self.pasta.mkdir(parents=True, exist_ok=True)
            agora = self.agora()
            base = f"loja-{agora:%Y-%m-%d-%H%M%S}"
            destino = self.pasta / f"{base}.db"
            n = 1
            while destino.exists():
                destino = self.pasta / f"{base}-{n}.db"
                n += 1
            temporario = destino.with_name(destino.name + ".tmp")
            try:
                self.loja.backup(str(temporario))
                self.loja.verificar_banco(temporario)
                os.replace(temporario, destino)
            finally:
                if temporario.exists():
                    temporario.unlink()
            status = {"data": agora.isoformat(timespec="seconds"), "arquivo": str(destino), "motivo": motivo,
                      "tamanho": destino.stat().st_size, "copia_extra": None, "erro_extra": None}
            extra = self.loja.obter_configuracoes().get("pasta_backup_extra")
            if extra:
                try:
                    copia = Path(extra) / destino.name
                    shutil.copy2(destino, copia)
                    status["copia_extra"] = str(copia)
                    self.limpar(extra)
                except OSError as e:
                    status["erro_extra"] = f"Não foi possível copiar para {extra}: {e.strerror or e}"
            self.limpar(self.pasta)
            self.loja.gravar_interno("ultimo_backup", json.dumps(status, ensure_ascii=False))
            return status

    def ultimo(self):
        valor = self.loja.ler_interno("ultimo_backup")
        return json.loads(valor) if valor else None

    def diario(self):
        """Faz o backup do dia se ainda não houver um."""
        hoje = f"loja-{self.agora():%Y-%m-%d}-"
        if not any(p.name.startswith(hoje) for p in self._arquivos(self.pasta)):
            return self.fazer("automático do dia")
        return None

    def restaurar(self, nome):
        if not PADRAO.match(str(nome)):
            raise LojaError("Backup inválido")
        caminho = self.pasta / nome
        if not caminho.is_file():
            raise LojaError("Backup não encontrado")
        self.loja.verificar_banco(caminho)
        seguranca = self.fazer("antes de restaurar")     # dá para desfazer a restauração
        self.loja.restaurar_de(caminho)
        return {"restaurado": nome, "copia_anterior": Path(seguranca["arquivo"]).name}

    # ---------------------------------------------------------- automático
    def iniciar_automatico(self, intervalo=1800):
        def laco():
            while not self._parar.wait(intervalo):
                try:
                    self.diario()
                except Exception:   # o backup nunca pode derrubar o sistema; o erro vai para o registro
                    traceback.print_exc()
        t = threading.Thread(target=laco, name="backup-automatico", daemon=True)
        t.start()
        return t

    def parar(self):
        self._parar.set()
