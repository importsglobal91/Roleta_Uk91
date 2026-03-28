import os
import asyncio
import random
from datetime import datetime
from typing import Dict, List
from dataclasses import dataclass
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Carrega TOKEN do .env (crie arquivo .env com TOKEN=seu_token)
TOKEN = os.getenv('TOKEN', '8657281596:AAE-wBWQnJgHctXEKn4lbD1XsEJCDfByNLA')

@dataclass
class EstadoRoleta:
    nome: str
    ultimo: str = None
    contagem: int = 0
    greens: int = 0
    hora_inicio: str = None
    rodadas: int = 0
    historico: List[int] = None  # Novo: histórico para 9V/9P

class BotMultiRoleta:
    def __init__(self):
        self.roletas: Dict[str, EstadoRoleta] = {}
        self.ativo = False
        self.context = None
        self.chat_id = None
        self.loop_tasks = []

        # Mesas 32Red reais (incluindo Red Door Roulette)
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

        # Links diretos das mesas (ajuste se algum nome/link for diferente no site)
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
            self.roletas[nome] = EstadoRoleta(nome=nome, historico=[])

    async def iniciar_monitoramento(self) -> bool:
        print("[LOG] Iniciando monitoramento multi-roleta 32Red...")
        hora = datetime.now().strftime("%H:%M:%S")
        for nome in self.roletas:
            self.roletas[nome].hora_inicio = hora
        self.ativo = True
        print(f"[✓] Monitorando {len(self.roletas)} roletas")
        return True

    async def gerar_numero_real(self, nome_roleta: str) -> int:
        """Futuro: Selenium scraper 32Red (integrado)"""
        # SIMULAÇÃO - substitua por selenium real
        return random.randint(0, 36)

    async def analisar_padrao(self, historico: List[int]) -> str:
        """Análise avançada: 9V/9P, Repetição, Street"""
        if len(historico) < 9:
            return "Aguardando padrão..."

        vermelhos = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
        ultimos9 = historico[-9:]
        v_count = sum(1 for n in ultimos9 if n in vermelhos)
        p_count = 9 - v_count

        if v_count == 9:
            return "🔴 9 VERMELHO - PRETO!"
        if p_count == 9:
            return "⚫ 9 PRETO - VERMELHO!"
        if len(set(ultimos9[-3:])) == 1:
            return "🔁 REPETIÇÃO 3x!"
        if ultimos9[-1] in {1,4,7,10,13,16,19,22,25,28,31,34}:
            return "🛣️ STREET 1-25!"
        return "Aguardando..."

    async def loop_analise_roleta(self, nome_roleta: str):
        print(f"[▶] Monitorando: {nome_roleta}")
        while self.ativo:
            try:
                numero = await self.gerar_numero_real(nome_roleta)
                await self.processar_numero(nome_roleta, numero)
                await asyncio.sleep(25)  # 25s por mesa
            except Exception as e:
                print(f"[✗] Erro {nome_roleta}: {e}")
                await asyncio.sleep(10)

    async def processar_numero(self, nome_roleta: str, numero: int):
        roleta = self.roletas[nome_roleta]
        numero_str = str(numero)
        roleta.historico.append(numero)
        if len(roleta.historico) > 20:  # Mantém 20 últimos
            roleta.historico.pop(0)

        if roleta.ultimo != numero_str:
            roleta.contagem = 1
            roleta.ultimo = numero_str
        else:
            roleta.contagem += 1
        roleta.rodadas += 1

        print(f"[{nome_roleta[:15]}] Nº:{numero} Seq:{roleta.contagem}x Rod:{roleta.rodadas}")

        # SINAIS múltiplos
        sinal = await self.analisar_padrao(roleta.historico)
        if "9 " in sinal or "REPETIÇÃO" in sinal or roleta.contagem >= 10:
            roleta.greens += 1

            link = self.links_mesas.get(
                nome_roleta,
                "https://www.32red.com/casino/live-casino/"
            )

            msg_sinal = (
                f"🟢 **SINAL {nome_roleta}!**\n"
                f"📊 Nº: {numero}\n"
                f"{sinal}\n"
                f"🟢 Total: {roleta.greens}\n\n"
                f"[🎰 Abrir mesa agora]({link})"
            )
            print(f"🟢 SINAL: {sinal}")
            if self.context and self.chat_id:
                await self.context.bot.send_message(
                    chat_id=self.chat_id,
                    text=msg_sinal,
                    parse_mode="Markdown"
                )

        if roleta.contagem >= 10:
            roleta.contagem = 0

    async def enviar_sinal(self, mensagem: str):
        try:
            await self.context.bot.send_message(
                chat_id=self.chat_id,
                text=mensagem,
                parse_mode="Markdown"
            )
            print("[✓] Sinal Telegram OK")
        except Exception as e:
            print(f"[✗] Telegram: {e}")

    def parar(self):
        self.ativo = False
        print("[⏹] Bot parado")

# Instância global
botauto = BotMultiRoleta()

# Comandos Telegram
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    botauto.chat_id = update.effective_chat.id
    botauto.context = context
    msg = (
        "🎰 **Bot 32Red v5.0 COMPLETO**\n\n"
        "/iniciar - mesas 24/7\n"
        "/status - Todas roletas\n"
        "/roletas - Lista mesas\n"
        "/parar - Stop\n\n"
        "✅ Pronto!"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def iniciar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if botauto.ativo:
        return await update.message.reply_text("❌ Já ativo!")
    await update.message.reply_text("⏳ Iniciando mesas...")
    sucesso = await botauto.iniciar_monitoramento()
    if sucesso:
        for nome in botauto.roletas:
            task = asyncio.create_task(botauto.loop_analise_roleta(nome))
            botauto.loop_tasks.append(task)
        await update.message.reply_text(
            "✅ **BOT LIGADO!** mesas ativas\nUse /status",
            parse_mode="Markdown"
        )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not botauto.ativo:
        return await update.message.reply_text("❌ Desligado. /iniciar")
    msg = "📊 **STATUS ROLETAS**\n\n"
    for nome, r in list(botauto.roletas.items())[:8]:  # Top 8 pra caber
        msg += f"🎰 {nome[:20]}: Seq {r.contagem}x | 🟢 {r.greens}\n"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def roletas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = "🎯 **Mesas 32Red**\n" + "\n".join(
        f"{i+1}. {nome}" for i, nome in enumerate(botauto.roletas_nomes)
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def parar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    botauto.parar()
    total = sum(r.greens for r in botauto.roletas.values())
    await update.message.reply_text(
        f"⏹️ Parado | 🟢 Total sinais: {total}",
        parse_mode="Markdown"
    )

def main():
    print("=" * 60)
    print("🎰 BOT 32RED v5.0 - COMPLETO")
    print(f"Roletas: {len(botauto.roletas)} | TOKEN: {'OK' if TOKEN else 'FALTA .env'}")
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
