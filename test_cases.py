"""Test runner — todas las capturas en modo APP celu (430x932)."""
import asyncio, json, os, sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

from playwright.async_api import async_playwright

BASE = "http://localhost:8000"
REPORT = []

P = lambda msg: REPORT.append(("PASS", msg))
F = lambda msg: REPORT.append(("FAIL", msg))
I = lambda msg: REPORT.append(("INFO", msg))

async def screenshot(page, name):
    os.makedirs("test_results", exist_ok=True)
    await page.screenshot(path=f"test_results/{name}.png", full_page=False)

async def login(page, username, password, wait_for):
    await page.goto(f"{BASE}/login", wait_until="networkidle")
    await page.wait_for_timeout(1000)
    await page.fill("#username", username)
    await page.fill("#password", password)
    await page.click("button[type=submit]")
    await page.wait_for_timeout(2000)

async def check_text(page, text, timeout=3000):
    try:
        await page.wait_for_selector(f"text={text}", timeout=timeout)
        return True
    except:
        return False

async def run():
    I(f"Iniciando pruebas: {datetime.now().isoformat()}")
    I(f"URL base: {BASE}")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)

        # Mobile viewport para TODOS los roles
        ctx = await browser.new_context(
            viewport={"width": 430, "height": 932},
            device_scale_factor=2,
        )
        page = await ctx.new_page()

        # ── 1. LANDING ──
        I("\n=== 1. LANDING ===")
        await page.goto(BASE, wait_until="networkidle")
        await page.wait_for_timeout(2000)
        if await check_text(page, "Estacionamiento Medido"):
            P("1.1 Landing carga con titulo correcto")
        else:
            F("1.1 Landing no muestra titulo")
        if await check_text(page, "Soy Conductor"):
            P("1.2 Landing muestra boton Soy Conductor")
        else:
            F("1.2 Landing no muestra boton Soy Conductor")
        if await check_text(page, "Soy Permisionario"):
            P("1.3 Landing muestra boton Soy Permisionario")
        else:
            F("1.3 Landing no muestra boton Soy Permisionario")
        await screenshot(page, "01_landing_test")

        # ── 2. LOGIN ──
        I("\n=== 2. LOGIN ===")
        await page.goto(f"{BASE}/login", wait_until="networkidle")
        await page.wait_for_timeout(1500)
        if await check_text(page, "Iniciar Sesion") or await check_text(page, "Usuario"):
            P("2.1 Login page carga")
        else:
            F("2.1 Login page no carga")
        await screenshot(page, "02_login_test")

        # ── 3. LOGIN CONDUCTOR ──
        I("\n=== 3. LOGIN CONDUCTOR ===")
        await login(page, "35123456", "1234", "conductor")
        if "conductor" in page.url:
            P("3.1 Login conductor redirige a /conductor")
        else:
            F(f"3.1 Redirigio a {page.url}")
        await screenshot(page, "03_conductor_home_test")

        # ── 4. CONDUCTOR HOME ──
        I("\n=== 4. CONDUCTOR HOME ===")
        await page.wait_for_timeout(3000)
        content = await page.content()
        if "timerDisplay" in content or "$" in content:
            P("4.1 Home carga con timer y costo (sesion activa JS-rendered)")
        else:
            F("4.1 Home no muestra indicadores de sesion")
        if "$" in content or "GRATIS" in content:
            P("4.2 Muestra costo/tarifa")
        else:
            F("4.2 No muestra costo")

        # ── 5. CONDUCTOR HISTORIAL ──
        I("\n=== 5. CONDUCTOR HISTORIAL ===")
        await page.goto(f"{BASE}/conductor/historial", wait_until="networkidle")
        await page.wait_for_timeout(2000)
        content = await page.content()
        if "AB123CD" in content:
            P("5.1 Historial muestra vehiculo/pedro")
        else:
            F("5.1 Historial no carga datos")
        if "finalizada" in content.lower() or "Finalizada" in content or "$" in content:
            P("5.2 Muestra sesiones finalizadas con costos")
        else:
            F("5.2 No muestra sesiones finalizadas")
        await screenshot(page, "05_historial_test")

        # ── 6. CONDUCTOR PERFIL ──
        I("\n=== 6. CONDUCTOR PERFIL ===")
        await page.goto(f"{BASE}/conductor/perfil", wait_until="networkidle")
        await page.wait_for_timeout(1500)
        if await check_text(page, "Pedro") or await check_text(page, "Lopez"):
            P("6.1 Perfil muestra datos del conductor")
        else:
            F("6.1 Perfil no muestra datos")
        if await check_text(page, "35123456"):
            P("6.2 Muestra DNI")
        else:
            F("6.2 No muestra DNI")
        await screenshot(page, "06_perfil_test")

        # ── 7. LOGIN INVALIDO ──
        I("\n=== 7. LOGIN INVALIDO ===")
        await page.goto(f"{BASE}/login", wait_until="networkidle")
        await page.wait_for_timeout(1000)
        await page.fill("#username", "35123456")
        await page.fill("#password", "wrongpass")
        await page.click("button[type=submit]")
        await page.wait_for_timeout(3000)
        error_shown = False
        try:
            await page.wait_for_selector("#errorMsg:not(:empty)", timeout=5000)
            error_shown = True
        except:
            pass
        if error_shown:
            P("7.1 Login invalido muestra error en pantalla")
        else:
            F("7.1 Login invalido no muestra error (url: {})".format(page.url))
        await screenshot(page, "07_login_error_test")

        # ── 8. CONDUCTOR DISCAPACIDAD ──
        I("\n=== 8. CONDUCTOR DISCAPACIDAD (gratis) ===")
        await login(page, "30111222", "1234", "conductor")
        if "conductor" in page.url:
            P("8.1 Login discapacidad exitoso")
        else:
            F("8.1 Login fallo")
        await page.goto(f"{BASE}/conductor/perfil", wait_until="networkidle")
        await page.wait_for_timeout(3000)
        nombre = await page.text_content("#campoNombre")
        if nombre and "Carlos" in nombre:
            P(f"8.2 Perfil carga datos de Carlos ({nombre})")
        else:
            F(f"8.2 Perfil no carga datos correctamente: {nombre}")
        await screenshot(page, "08_perfil_disc_test")

        # ── 9. CONDUCTOR BICICLETA ──
        I("\n=== 9. CONDUCTOR BICICLETA (gratis) ===")
        await login(page, "37555666", "1234", "conductor")
        if "conductor" in page.url:
            P("9.1 Login bicicleta exitoso")
        else:
            F("9.1 Login fallo")
        await page.goto(f"{BASE}/conductor/vehiculos", wait_until="networkidle")
        await page.wait_for_timeout(4000)
        content = await page.content()
        if "BI001BICI" in content or "bicicleta" in content.lower():
            P("9.2 Vehiculos muestra bicicleta (BI001BICI)")
        else:
            F("9.2 No encuentra patente de bicicleta en vehiculos")
        await screenshot(page, "09_vehiculos_bici_test")

        # ── 10. PERMISIONARIO ──
        I("\n=== 10. PERMISIONARIO (mobile) ===")
        await login(page, "PER30456789", "1234", "permisionario")
        if "permisionario" in page.url:
            P("10.1 Login permisionario redirige a /permisionario")
        else:
            F(f"10.1 Redirigio a {page.url}")
        await page.goto(f"{BASE}/permisionario/panel", wait_until="networkidle")
        await page.wait_for_timeout(2000)
        if await check_text(page, "Gral") or await check_text(page, "GUEMES") or await check_text(page, "Panel"):
            P("10.2 Panel permisionario carga con datos")
        else:
            F("10.2 Panel no carga")
        await screenshot(page, "10_permisionario_panel_test")

        # ── 11. PERMISIONARIO ESPACIOS (mobile) ──
        I("\n=== 11. PERMISIONARIO ESPACIOS (mobile) ===")
        await page.goto(f"{BASE}/permisionario/espacios", wait_until="networkidle")
        await page.wait_for_timeout(2000)
        if await check_text(page, "Espacio") or await check_text(page, "espacio") or await check_text(page, "GUEMES"):
            P("11.1 Espacios carga con datos")
        else:
            F("11.1 Espacios no carga correctamente")
        await screenshot(page, "11_espacios_test")

        # ── 12. PERMISIONARIO QR (mobile) ──
        I("\n=== 12. PERMISIONARIO QR (mobile) ===")
        await page.goto(f"{BASE}/permisionario/qr", wait_until="networkidle")
        await page.wait_for_timeout(2000)
        if await check_text(page, "QR") or await check_text(page, "qr"):
            P("12.1 Pagina QR carga")
        else:
            F("12.1 QR no carga")
        await screenshot(page, "12_qr_test")

        # ── 13. GESTOR (mobile) ──
        I("\n=== 13. GESTOR (mobile) ===")
        await login(page, "gestor1", "gestor123", "gestor")
        if "gestor" in page.url:
            P("13.1 Login gestor redirige a /gestor")
        else:
            F(f"13.1 Redirigio a {page.url}")
        await page.goto(f"{BASE}/gestor", wait_until="networkidle")
        await page.wait_for_timeout(2000)
        if await check_text(page, "Dashboard") or await check_text(page, "Gestor"):
            P("13.2 Dashboard gestor carga")
        else:
            F("13.2 Dashboard gestor no carga")
        await screenshot(page, "13_gestor_test")

        # ── 14. ADMIN (mobile) ──
        I("\n=== 14. ADMIN (mobile) ===")
        await login(page, "admin", "admin123", "admin")
        if "admin" in page.url:
            P("14.1 Login admin redirige a /admin")
        else:
            F(f"14.1 Redirigio a {page.url}")
        await page.goto(f"{BASE}/admin", wait_until="networkidle")
        await page.wait_for_timeout(2000)
        if await check_text(page, "Dashboard") or await check_text(page, "Admin"):
            P("14.2 Dashboard admin carga")
        else:
            F("14.2 Dashboard admin no carga")
        await screenshot(page, "14_admin_test")

        # ── 15. ADMIN CONDUCTORES (mobile) ──
        I("\n=== 15. ADMIN CONDUCTORES (mobile) ===")
        await page.goto(f"{BASE}/admin/conductores", wait_until="networkidle")
        await page.wait_for_timeout(2000)
        content = await page.content()
        if "35123456" in content and "30111222" in content:
            P("15.1 Lista conductores muestra DNI de todos")
        else:
            F("15.1 No muestra todos los conductores")
        await screenshot(page, "15_admin_conductores_test")

        # ── 16. ADMIN DEUDAS (mobile) ──
        I("\n=== 16. ADMIN DEUDAS (mobile) ===")
        await page.goto(f"{BASE}/admin/deudas", wait_until="networkidle")
        await page.wait_for_timeout(2000)
        if await check_text(page, "2400") or await check_text(page, "900"):
            P("16.1 Deudas muestra montos y registros")
        else:
            F("16.1 No muestra deudas correctamente")
        await screenshot(page, "16_admin_deudas_test")

        # ── 17. ADMIN SESIONES (mobile) ──
        I("\n=== 17. ADMIN SESIONES (mobile) ===")
        await page.goto(f"{BASE}/admin/sesiones", wait_until="networkidle")
        await page.wait_for_timeout(2000)
        if await check_text(page, "Activa") or await check_text(page, "activa"):
            P("17.1 Mapa de sesiones activas carga")
        else:
            F("17.1 Sesiones activas no se muestran")
        await screenshot(page, "17_admin_sesiones_test")

        # ── 18. ADMIN REPORTES (mobile) ──
        I("\n=== 18. ADMIN REPORTES (mobile) ===")
        await page.goto(f"{BASE}/admin/reportes", wait_until="networkidle")
        await page.wait_for_timeout(2000)
        if await check_text(page, "Reporte") or await check_text(page, "reporte"):
            P("18.1 Reportes carga")
        else:
            F("18.1 Reportes no carga")
        await screenshot(page, "18_reportes_test")

        # ── 19. VERIFY EMAIL (mobile) ──
        I("\n=== 19. VERIFY EMAIL (mobile) ===")
        await page.goto(f"{BASE}/api/auth/verify-email?token=demo", wait_until="networkidle")
        await page.wait_for_timeout(2000)
        if await check_text(page, "Error de verificación") or await check_text(page, "error"):
            P("19.1 Token invalido muestra mensaje de error")
        else:
            F("19.1 Token invalido no muestra error esperado")
        await screenshot(page, "19_verify_invalid_test")

        await ctx.close()
        await browser.close()

    # ── Report ──
    I("\n" + "=" * 60)
    I("RESULTADOS DE PRUEBAS")
    I("=" * 60)
    passed = sum(1 for r in REPORT if r[0] == "PASS")
    failed = sum(1 for r in REPORT if r[0] == "FAIL")
    for status, msg in REPORT:
        icon = {"PASS": "✅", "FAIL": "❌", "INFO": "ℹ️"}[status]
        print(f"  {icon} {msg}")
    I(f"\nTotal: {passed} pasaron, {failed} fallaron de {len(REPORT)}")

    report_path = "test_results/reporte_pruebas.json"
    os.makedirs("test_results", exist_ok=True)
    with open(report_path, "w") as f:
        json.dump({
            "date": datetime.now().isoformat(),
            "base_url": BASE,
            "viewport": "430x932 (mobile)",
            "results": [{"status": s, "message": m} for s, m in REPORT],
            "summary": {"passed": passed, "failed": failed, "total": len(REPORT)}
        }, f, indent=2, ensure_ascii=False)
    print(f"\nReporte guardado en {report_path}")


if __name__ == "__main__":
    asyncio.run(run())
