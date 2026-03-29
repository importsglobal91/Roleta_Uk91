import os
import asyncio
import random
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# TOKEN do bot
TOKEN = os.getenv("8657281596:AAExL5uCblF4v2AaA0lnYPEF0cPesXVqkRA")

# NOME DA SUA SALA / CABEÇALHO DAS MENSAGENS
NOME_SALA = "Roleta__"


# ---------------- MODELOS DE ESTADO ----------------

@dataclass
class EstadoRoleta:
    nome: str
    historico: List[int] = field(default_factory=list)
    hora_inicio: Optional[str] = None
    rodadas: int = 0

    padrao_atual: Optional[str] = None
    em_analise: bool = False
    entrada_em_andamento: bool = False
    tentativas_restantes: int = 0

    greens: int = 0
    reds: int = 0
    greens_seguidos: int = 0


@dataclass
class EstatisticasGlobais:
    greens: int = 0
    reds: int = 0
    greens_seguidos: int = 0

    def registrar_green(self):
        self.greens += 1
        self.greens_seguidos += 1

    def registrar_red(self):
        self.reds += 1
        self.greens_seguidos = 0

    @property
    def total(self) -> int:
        return self.greens + self.reds

    @property
    def porcentagem(self) -> float:
        return (self.greens / self.total * 100) if self.total > 0 else 0.0


# ---------------- BOT MULTI ROLETAS ----------------

class BotMultiRoleta:
    def __init__(self):
        self.roletas: Dict[str, EstadoRoleta] = {}
        self.ativo = False
        self.context: Optional[ContextTypes.DEFAULT_TYPE] = None
        self.chat_id: Optional[int] = None
        self.loop_tasks: List[asyncio.Task] = []
        self.estatisticas = EstatisticasGlobais()

        self.roletas_nomes = [
            "Roleta 32Vermelha",
            "Lightning Roulette",
            "Quantum Roulette",
            "Auto Roulette",
            "VIP Roulette",
            "Dragonara Roulette",
            "French Roulette",
            "American Roulette",
            "Mega Roulette",
            "Speed Roulette",
            "Immersive Roulette",
            "Slingshot Auto",
            "Double Ball Roulette",
            "Crazy Time Roulette",
            "Red Door Roulette",
        ]

        self.links_mesas = {
            "Roleta 32Vermelha": "https://www.32red.com/play/32red-roulette#playforreal",
            "Lightning Roulette": "https://www.32red.com/play/lightning-roulette#playforreal",
            "Quantum Roulette": "https://www.32red.com/play/quantum-roulette#playforreal",
            "Auto Roulette": "https://www.32red.com/play/auto-roulette#playforreal",
            "VIP Roulette": "https://www.32red.com/play/vip-roulette#playforreal",
            "Dragonara Roulette": "https://www.32red.com/play/dragonara-roulette#playforreal",
            "French Roulette": "https://www.32red.com/play/french-roulette#playforreal",
            "American Roulette": "https://www.32red.com/play/american-roulette#playforreal",
            "Mega Roulette": "https://www.32red.com/play/mega-roulette#playforreal",
            "Speed Roulette": "https://www.32red.com/play/speed-roulette#playforreal",
            "Immersive Roulette": "https://www.32red.com/play/immersive-roulette#playforreal",
            "Slingshot Auto": "https://www.32red.com/play/slingshot-auto-roulette#playforreal",
            "Double Ball Roulette": "https://www.32red.com/play/double-ball-roulette#playforreal",
            "Crazy Time Roulette": "https://www.32red.com/play/crazy-time#playforreal",
            "Red Door Roulette": "https://www.32red.com/play/red-door-roulette#playforreal",
        }

        for nome in self.roletas_nomes:
            self.roletas[nome] = EstadoRoleta(nome=nome)

    # ----------- SIMULAÇÃO / TROCAR PELA SUA CAPTURA REAL -----------

    async def gerar_numero_real(self, nome_roleta: str) -> int:
        return random.randint(0, 36)

    # ----------- CLASSIFICAÇÃO DOS NÚMEROS -----------

    def classificar_padrao(self, numero: int) -> Dict[str, str]:
        if numero == 0:
            return {"paridade": "ZERO", "cor": "ZERO", "faixa": "ZERO"}

        paridade = "PAR" if numero % 2 == 0 else "IMPAR"
        vermelhos = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
        cor = "VERMELHO" if numero in vermelhos else "PRETO"
        faixa = "BAIXO" if 1 <= numero <= 18 else "ALTO"

        return {"paridade": paridade, "cor": cor, "faixa": faixa}

    def determinar_padrao(self, ultimos: List[int]) -> Optional[str]:
        if len(ultimos) < 10:
            return None

        infos = [self.classificar_padrao(n) for n in ultimos[-10:]]

        if any(info["paridade"] == "ZERO" for info in infos):
            return None

        if all(info["paridade"] == infos[0]["paridade"] for info in infos):
            return infos[0]["paridade"]

        if all(info["cor"] == infos[0]["cor"] for info in infos):
            return infos[0]["cor"]

        if all(info["faixa"] == infos[0]["faixa"] for info in infos):
            return infos[0]["faixa"]

        return None

    def contrario_do_padrao(self, padrao: str) -> str:
        mapa = {
            "PAR": "IMPAR",
            "IMPAR": "PAR",
            "VERMELHO": "PRETO",
            "PRETO": "VERMELHO",
            "ALTO": "BAIXO",
            "BAIXO": "ALTO",
        }
        return mapa.get(padrao, "DESCONHECIDO")

    def nome_estrategia_formatado(self, padrao: str) -> str:
        mapa = {
            "PAR": "Repetição de Pares",
            "IMPAR": "Repetição de Ímpares",
            "VERMELHO": "Repetição de Vermelhos",
            "PRETO": "Repetição de Pretos",
            "ALTO": "Repetição de Altos",
            "BAIXO": "Repetição de Baixos",
        }
        return mapa.get(padrao, f"Repetição de {padrao.title()}")

    def texto_aposta(self, padrao: str) -> str:
        alvo = self.contrario_do_padrao(padrao)
        mapa = {
            "PAR": "números pares",
            "IMPAR": "números ímpares",
            "VERMELHO": "vermelho",
            "PRETO": "preto",
            "ALTO": "alto",
            "BAIXO": "baixo",
        }
        return mapa.get(alvo, alvo.lower())

    # ----------- ENVIO DE MENSAGENS -----------

    async def enviar_mensagem(self, texto: str):
        if self.context and self.chat_id:
            await self.context.bot.send_message(
                chat_id=self.chat_id,
                text=texto,
                parse_mode="Markdown",
                disable_web_page_preview=True,
            )

    async def enviar_entrada_confirmada(
        self, r: EstadoRoleta, padrao: str, numero: int, tentativa: int
    ):
        estrategia = self.nome_estrategia_formatado(padrao)
        seq = " | ".join(str(n) for n in r.historico[-10:])
        aposta = self.texto_aposta(padrao)

        msg = (
            f"*{NOME_SALA}*\n"
            f"💰 *ENTRADA CONFIRMADA* 💰\n\n"
            f"🎲 Estratégia: {estrategia}\n"
            f"🎰 Mesa: {r.nome}\n"
            f"🚦 Sequência: {seq}\n\n"
            f"💰 Entrar após o {numero} apostar em {aposta}\n"
            f"👉 Cobrir o zero\n"
            f"🔁 Fazer até 2 gales"
        )
        await self.enviar_mensagem(msg)

    async def enviar_green(self, numero: int):
        msg = f"✅✅✅ *GREEN!!!* 👍 ({numero})"
        await self.enviar_mensagem(msg)

    async def enviar_red(self):
        msg = "❌ *RED*"
        await self.enviar_mensagem(msg)

    async def enviar_resultado(self, green: bool):
        if green:
            self.estatisticas.registrar_green()
        else:
            self.estatisticas.registrar_red()

        msg = (
            f"🚀 *Placar do dia* 🟢 {self.estatisticas.greens} 🔴 {self.estatisticas.reds}\n"
            f"🎯 Acertamos {self.estatisticas.porcentagem:.2f}% das vezes\n"
            f"💰 Estamos com {self.estatisticas.greens_seguidos} Greens seguidos!"
        )
        await self.enviar_mensagem(msg)

    # ----------- PROCESSAMENTO -----------

    async def processar_numero(self, nome_roleta: str, numero: int):
        r = self.roletas[nome_roleta]
        r.historico.append(numero)

        if len(r.historico) > 40:
            r.historico.pop(0)

        r.rodadas += 1
        info = self.classificar_padrao(numero)

        print(
            f"[{nome_roleta[:15]}] Nº:{numero} "
            f"({info['paridade']},{info['cor']},{info['faixa']}) "
            f"Rod:{r.rodadas}"
        )

        if not r.entrada_em_andamento:
            padrao = self.determinar_padrao(r.historico)

            if padrao:
                if not r.em_analise:
                    r.padrao_atual = padrao
                    r.em_analise = True
                    r.entrada_em_andamento = True
                    r.tentativas_restantes = 3

                    await self.enviar_entrada_confirmada(r, padrao, numero, 1)
            else:
                r.padrao_atual = None
                r.em_analise = False
                r.entrada_em_andamento = False
                r.tentativas_restantes = 0

        else:
            alvo = self.contrario_do_padrao(r.padrao_atual)
            ganhou = False

            if alvo in {"PAR", "IMPAR"}:
                ganhou = info["paridade"] == alvo
            elif alvo in {"VERMELHO", "PRETO"}:
                ganhou = info["cor"] == alvo
            elif alvo in {"ALTO", "BAIXO"}:
                ganhou = info["faixa"] == alvo

            if ganhou:
                r.greens += 1
                r.greens_seguidos += 1

                print(f"[{nome_roleta[:15]}] GREEN!")
                await self.enviar_green(numero)
                await self.enviar_resultado(True)

                r.padrao_atual = None
                r.em_analise = False
                r.entrada_em_andamento = False
                r.tentativas_restantes = 0

            else:
                r.tentativas_restantes -= 1

                if r.tentativas_restantes > 0:
                    tentativa_feita = 4 - r.tentativas_restantes
                    await self.enviar_entrada_confirmada(
                        r, r.padrao_atual, numero, tentativa_feita
                    )
                else:
                    r.reds += 1
                    r.greens_seguidos = 0

                    print(f"[{nome_roleta[:15]}] RED!")
                    await self.enviar_red()
                    await self.enviar_resultado(False)

                    r.padrao_atual = None
                    r.em_analise = False
                    r.entrada_em_andamento = False
                    r.tentativas_restantes = 0

    async def loop_analise_roleta(self, nome_roleta: str):
        print(f"[▶] Monitorando: {nome_roleta}")
        while self.ativo:
            try:
                numero = await self.gerar_numero_real(nome_roleta)
                await self.processar_numero(nome_roleta, numero)
                await asyncio.sleep(2)
            except Exception as e:
                print(f"[✗] Erro {nome_roleta}: {e}")
                await asyncio.sleep(10)

    async def iniciar_monitoramento(self) -> bool:
        print("[LOG] Iniciando monitoramento multi-roleta 32Red...")
        hora = datetime.now().strftime("%H:%M:%S")

        for nome in self.roletas:
            self.roletas[nome].hora_inicio = hora

        self.ativo = True
        print(f"[✓] Monitorando {len(self.roletas)} roletas")
        return True

    def parar(self):
        self.ativo = False
        print("[⏹] Bot parado")


botauto = BotMultiRoleta()

# ---------------- COMANDOS TELEGRAM ----------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    botauto.chat_id = update.effective_chat.id
    botauto.context = context

    msg = (
        f"🎰 *{NOME_SALA}*\n\n"
        "/iniciar - Ligar monitoramento\n"
        "/status  - Ver roletas\n"
        "/roletas - Listar mesas\n"
        "/parar   - Stop\n\n"
        "✅ Pronto para analisar as mesas."
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def iniciar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if botauto.ativo:
        return await update.message.reply_text("❌ Já está ativo.")

    await update.message.reply_text("⏳ Iniciando mesas...")
    sucesso = await botauto.iniciar_monitoramento()

    if sucesso:
        for nome in botauto.roletas:
            task = asyncio.create_task(botauto.loop_analise_roleta(nome))
            botauto.loop_tasks.append(task)

        await update.message.reply_text(
            "✅ *BOT LIGADO!* Mesas ativas.\nUse /status para ver.",
            parse_mode="Markdown",
        )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not botauto.ativo:
        return await update.message.reply_text("❌ Desligado. Use /iniciar.")

    msg = "📊 *STATUS ROLETAS (top 8)*\n\n"
    for nome, r in list(botauto.roletas.items())[:8]:
        msg += (
            f"🎰 {nome[:20]}: "
            f"Rod {r.rodadas} | 🟢 {r.greens} 🔴 {r.reds} | "
            f"Seq greens: {r.greens_seguidos}\n"
        )

    await update.message.reply_text(msg, parse_mode="Markdown")


async def roletas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "🎯 *Mesas 32Red*\n" + "\n".join(
        f"{i+1}. {nome}" for i, nome in enumerate(botauto.roletas_nomes)
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def parar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    botauto.parar()
    total = botauto.estatisticas.total

    msg = (
        f"⏹️ Bot parado.\n"
        f"🟢 Greens: {botauto.estatisticas.greens} "
        f"🔴 Reds: {botauto.estatisticas.reds}\n"
        f"🎯 Acerto: {botauto.estatisticas.porcentagem:.2f}% (total {total})"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")


def main():
    print("=" * 60)
    print("🎰 BOT 32RED v5.0 - COMPLETO")
    print(
        f"Roletas: {len(botauto.roletas)} | TOKEN: "
        f"{'OK' if TOKEN and TOKEN != '8657281596:AAE-wBWQnJgHctXEKn4lbD1XsEJCDfByNLA' else 'FALTA .env/TOKEN'}"
    )
    print("=" * 60)

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("iniciar", iniciar))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("roletas", roletas))
    app.add_handler(CommandHandler("parar", parar))

    print("[▶] Bot online...")
    app.run_polling()


if __name__ == "__main__":
    main()
