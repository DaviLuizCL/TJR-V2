async def test_preflight_permite_origem_do_frontend_dev(client):
    response = await client.options(
        "/api/v1/eventos",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


async def test_resposta_real_inclui_header_cors_para_origem_permitida(client):
    response = await client.get("/api/v1/health", headers={"Origin": "http://localhost:5173"})

    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
