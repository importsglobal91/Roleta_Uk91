import os
import asyncio
import random
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# TOKEN do bot (pode vir do .env)
TOKEN = os.getenv("TOKEN", "8657281596:AAE-wBWQnJgHctXEKn4lbD1XsEJCDfByNLA ")

# ---------------- MODELOS DE ESTADO ----------------

@dataclass
class EstadoRoleta:
    nome: str
    historico: List[int] = field(default_factory=list)      # últimos números
    hora_inicio: Optional[str] = None
    rodadas: int = 0

    # estado da sequência de repetição
    padrao_atual: Optional[str] = None       # "PAR", "IMPAR", "VERMELHO", "PRETO", "ALTO", "BAIXO"
    em_analise: bool = False                # já mandamos mensagem ANALISANDO
    entrada_em_andamento: bool = False      # já estamos nas tentativas (11ª em diante)
    tentativas_restantes: int = 0           # 3 → 1ª, 2ª, 3ª entrada

    # estatísticas por mesa
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

        # Mesas 32Red
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

        # Links diretos das mesas
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

    # ----------- SIMULAÇÃO (trocar depois por números reais) -----------

    async def gerar_numero_real(self, nome_roleta: str) -> int:
        # Futuro: integrar Selenium / API da 32Red
        return random.randint(0, 36)

    # ----------- CLASSIFICAÇÃO DOS NÚMEROS -----------

    def classificar_padrao(self, numero: int) -> Dict[str, str]:
        if numero == 0:
            return {"paridade": "ZERO", "cor": "ZERO", "faixa": "ZERO"}

        paridade = "PAR" if numero % 2 == 0 else "IMPAR"
        vermelhos = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
        cor = "VERMELHO" if numero in vermelhos else "PRETO"
        faixa = "BAIXO" if 1 <= numero <= 18 else "ALTO"

        return {"paridade": paridade, "cor": cor, "faixa": faixa}

    # ----------- LÓGICA DA ESTRATÉGIA -----------

    def determinar_padrao(self, ultimos: List[int]) -> Optional[str]:
        """Vê se os 10 últimos seguem um mesmo padrão em paridade/cor/faixa."""
        if len(ultimos) < 10:
            return None

        infos = [self.classificar_padrao(n) for n in ultimos[-10:]]
        # ignora zeros
        if any(info["paridade"] == "ZERO" for info in infos):
            return None

        # checa repetição em paridade
        if all(info["paridade"] == infos[0]["paridade"] for info in infos):
            return infos[0]["paridade"]  # "PAR" ou "IMPAR"

        # repetição em cor
        if all(info["cor"] == infos[0]["cor"] for info in infos):
            return infos[0]["cor"]  # "VERMELHO" ou "PRETO"

        # repetição em faixa
        if all(info["faixa"] == infos[0]["faixa"] for info in infos):
            return infos[0]["faixa"]  # "ALTO" ou "BAIXO"

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

    async def enviar_mensagem(self, texto: str):
        if self.context and self.chat_id:
            await self.context.bot.send_message(
                chat_id=self.chat_id,
                text=texto,
                parse_mode="Markdown",
                disable_web_page_preview=True,  # não precisa preview do link
            )

    async def enviar_analise(self, r: EstadoRoleta, padrao: str):
        """Mensagem enviada apenas quando entra em análise (depois de 10 números)."""
        seq = " | ".join(str(n) for n in r.historico[-10:])
        link = self.links_mesas.get(
            r.nome, "https://www.32red.com/casino/live-casino/"
        )

        msg = (
            "🚨 *ANALISANDO* 🚨\n\n"
            f"🎯 Estratégia: Repetição de *{padrao.title()}*\n"
            f"🎰 Mesa: [32Red — {r.nome}]({link})\n"
            f"🔗 Link direto: {link}\n"
            f"🚦 Sequência: {seq}\n"
            "💰 Entrar ao contrário na 11ª jogada\n"
            "💵 Cobrir o zero\n"
            "♻️ Fazer até 3 entradas\n"
        )
        await self.enviar_mensagem(msg)

    async def enviar_entrada_confirmada(
        self, r: EstadoRoleta, padrao: str, numero: int, tentativa: int
    ):
        alvo = self.contrario_do_padrao(padrao)
        link = self.links_mesas.get(
            r.nome, "https://www.32red.com/casino/live-casino/"
        )
        msg = (
            "✅ *ENTRADA CONFIRMADA* ✅\n\n"
            f"🎯 Estratégia: Repetição de *{padrao.title()}*\n"
            f"🎰 Mesa: [32Red — {r.nome}]({link})\n"
            f"🔗 Link direto: {link}\n"
            f"🎲 Último número: {numero}\n"
            f"🎯 Entrar em: *{alvo}* (tentativa {tentativa}/3)\n"
            "💵 Cobrir o zero\n"
        )
        await self.enviar_mensagem(msg)

    async def enviar_resultado(self, green: bool):
        if green:
            self.estatisticas.registrar_green()
        else:
            self.estatisticas.registrar_red()

        msg = (
            f"📈 *Placar do dia* 🟢 {self.estatisticas.greens} 🔴 {self.estatisticas.reds}\n"
            f"🎯 Acertamos {self.estatisticas.porcentagem:.2f}% das vezes\n"
            f"🟢 Estamos com {self.estatisticas.greens_seguidos} Greens seguidos!\n"
        )
        await self.enviar_mensagem(msg)

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

        # Já estamos em uma sequência observada?
        if not r.entrada_em_andamento:
            padrao = self.determinar_padrao(r.historico)
            if padrao:
                # Entrou condição dos 10 últimos: manda APENAS ANALISANDO
                if not r.em_analise:
                    r.padrao_atual = padrao
                    r.em_analise = True
                    r.tentativas_restantes = 3
                    await self.enviar_analise(r, padrao)
                else:
                    # Já está em análise; na próxima (11ª em diante) começa entrada
                    if len(r.historico) >= 11 and not r.entrada_em_andamento:
                        r.entrada_em_andamento = True
                        await self.enviar_entrada_confirmada(
                            r, r.padrao_atual, numero, 1
                        )
            else:
                r.padrao_atual = None
                r.em_analise = False
        else:
            # já estamos nas tentativas
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
                await self.enviar_mensagem("✅✅✅ *GREEN!!!*")
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
                    await self.enviar_mensagem("❌ *RED nessa sequência*")
                    await self.enviar_resultado(False)
                    r.padrao_atual = None
                    r.em_analise = False
                    r.entrada_em_andamento = False

    async def loop_analise_roleta(self, nome_roleta: str):
        print(f"[▶] Monitorando: {nome_roleta}")
        while self.ativo:
            try:
                numero = await self.gerar_numero_real(nome_roleta)
                await self.processar_numero(nome_roleta, numero)
                await asyncio.sleep(2)  # mais rápido para simulação
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
        "🎰 *Bot 32Red v5.0 COMPLETO*\n\n"
        "/iniciar - Ligar monitoramento\n"
        "/status  - Ver roletas\n"
        "/roletas - Listar mesas\n"
        "/parar   - Stop\n\n"
        "✅ Pronto para analisar 10 giros e entrar na 11ª com 3 tentativas."
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
        f"{'OK' if TOKEN and TOKEN != 'SEU_TOKEN_AQUI' else 'FALTA .env/TOKEN'}"
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
