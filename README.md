# Radar de Oportunidades Crossover — V2

Aplicação pronta para Vercel com pesquisa web real via Tavily.

## Publicar na Vercel
1. Crie um projeto na Vercel e envie esta pasta (preferencialmente via GitHub, ou Vercel CLI).
2. Em **Settings → Environment Variables**, crie `TAVILY_API_KEY` e cole sua chave Tavily.
3. Marque Production, Preview e Development se quiser usar em todos os ambientes.
4. Faça um novo deploy.
5. Abra a URL gerada e teste uma empresa.

## Segurança
- Nunca coloque a chave Tavily no `index.html`.
- `.env.example` contém apenas um exemplo e pode ser versionado.
- O backend lê `TAVILY_API_KEY` somente no servidor.

## O que a análise faz
- executa buscas separadas para sinais, vagas, liderança, expansão/governança e decisores públicos;
- consolida fontes sem duplicidade;
- calcula um índice interno de oportunidade de 0 a 10;
- sugere CICS, ABR ou ERM por aderência textual;
- tenta localizar decisores em resultados públicos, priorizando cargos de liderança;
- gera duas abordagens: momento da empresa e insight do decisor.

## Limites desta V2
A localização de decisores depende do que estiver publicamente indexado. O sistema não faz scraping não autorizado do LinkedIn. Sempre confira cargo e vínculo na fonte antes de abordar.
