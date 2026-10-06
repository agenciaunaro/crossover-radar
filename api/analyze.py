import os, re, json, requests
from flask import Flask, request, jsonify, send_from_directory
from urllib.parse import urlparse

app = Flask(__name__)
TAVILY_URL = 'https://api.tavily.com/search'

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

@app.route('/')
def home():
    return send_from_directory(ROOT_DIR, 'index.html')

@app.route('/logo.png')
def logo():
    return send_from_directory(ROOT_DIR, 'logo.png')

SIGNALS = [
 ('lideranca','Nova liderança em Auditoria, Riscos, Controles, Compliance ou Governança',3,['nova liderança','assumiu','nomeado','nomeada','diretor','diretora','head','superintendente']),
 ('vagas','Vagas em Auditoria, Riscos, Controles, Compliance ou Governança',3,['vaga','vagas','hiring','contratando','carreiras','jobs']),
 ('governanca','Governança, riscos ou controles como prioridade',3,['governança','gestão de riscos','controles internos','auditoria interna','compliance']),
 ('expansao','Expansão, aquisição, reestruturação ou transformação',2,['expansão','aquisição','fusão','reestruturação','nova unidade','transformação']),
 ('regulatorio','Movimentação regulatória relevante',2,['regulação','regulatório','regulatória','norma','resolução','bacen','cvm','susep']),
 ('desenvolvimento','Desenvolvimento de pessoas ou educação corporativa',2,['treinamento','desenvolvimento','universidade corporativa','capacitação','educação corporativa']),
 ('planejamento','Planejamento ou prioridades para 2027',2,['2027','planejamento estratégico','prioridades estratégicas'])
]

def tavily(query, key, max_results=5, topic='general'):
    payload={'api_key':key,'query':query,'search_depth':'advanced','max_results':max_results,'include_answer':'basic','include_raw_content':False,'topic':topic}
    r=requests.post(TAVILY_URL,json=payload,timeout=35); r.raise_for_status(); return r.json()

def domain(url):
    try: return urlparse(url).netloc.replace('www.','')
    except: return ''

def dedupe(results):
    out=[]; seen=set()
    for x in results:
        u=x.get('url','')
        if not u or u in seen: continue
        seen.add(u); out.append(x)
    return out

def find_people(results, company):
    relevant_roles = re.compile(
        r'(auditoria|audit|riscos|risk|controles internos|internal controls|'
        r'compliance|governança|governance|treinamento|training|'
        r'desenvolvimento|learning|recursos humanos|human resources|'
        r'people|talentos|corporate university)',
        re.I
    )

    seniority = re.compile(
        r'(diretor(?:a)?|director|head|gerente|manager|'
        r'superintendente|superintendent|coordenador(?:a)?|coordinator|'
        r'chief|vp|vice president)',
        re.I
    )

    people = []
    seen = set()

    for r in results:
        url = (r.get('url') or '').strip()
        title = (r.get('title') or '').strip()
        content = (r.get('content') or '').strip()

        # REGRA RÍGIDA:
        # somente perfis pessoais públicos do LinkedIn
        if not re.search(r'https?://([a-z]{2,3}\.)?linkedin\.com/in/', url, re.I):
            continue

        text = f'{title} {content}'

        # precisa ter relação com uma área compradora da Crossover
        if not relevant_roles.search(text):
            continue

        # prioriza cargos com poder de decisão/influência
        if not seniority.search(text):
            continue

        # tenta extrair o nome do título do resultado
        clean_title = re.sub(r'\s*\|\s*LinkedIn.*$', '', title, flags=re.I)
        parts = [
            p.strip()
            for p in re.split(r'\s[-–—|]\s', clean_title)
            if p.strip()
        ]

        if not parts:
            continue

        name = parts[0].strip()

        # bloqueia documentos, relatórios e páginas que não sejam pessoas
        forbidden = [
            'relatório', 'report', 'estrutura', 'política',
            'policy', 'ética', 'compliance e esg',
            'por que', 'notícia', 'news', 'vagas',
            'jobs', 'carreiras', 'careers'
        ]

        if any(word in name.lower() for word in forbidden):
            continue

        # nome precisa parecer nome de pessoa
        words = name.split()
        if len(words) < 2 or len(words) > 6:
            continue

        if len(name) > 80:
            continue

        # evita duplicidade
        profile_key = url.lower().split('?')[0].rstrip('/')
        if profile_key in seen:
            continue

        seen.add(profile_key)

        role = 'Profissional relacionado à área'

        if len(parts) >= 2:
            role = parts[1][:140]

        # se o segundo trecho não trouxer cargo, tenta extrair do conteúdo
        if role == 'Profissional relacionado à área' or not relevant_roles.search(role):
            m = re.search(
                r'((?:diretor(?:a)?|director|head|gerente|manager|'
                r'superintendente|superintendent|coordenador(?:a)?|coordinator|'
                r'chief|vp|vice president).{0,100}'
                r'(?:auditoria|audit|riscos|risk|controles|compliance|'
                r'governança|governance|treinamento|training|'
                r'desenvolvimento|learning|recursos humanos|people|talentos))',
                text,
                re.I
            )
            if m:
                role = m.group(1).strip(' -–—|,.;')[:140]

        priority = (
            'ALTA'
            if re.search(
                r'diretor|director|head|superintendente|chief|vp|vice president',
                role,
                re.I
            )
            else 'MÉDIA'
        )

        area = 'Decisor técnico'

        if re.search(
            r'treinamento|training|desenvolvimento|learning|'
            r'recursos humanos|human resources|people|talentos',
            text,
            re.I
        ):
            area = 'RH / T&D / People'

        people.append({
            'name': name,
            'role': role,
            'area': area,
            'company': company,
            'priority': priority,
            'url': url,
            'source': 'LinkedIn',
            'verified': True
        })

        if len(people) >= 6:
            break

    return people
      
def solution_from_text(text):
    scores={'CICS':0,'ABR':0,'ERM':0}
    for w in ['controle interno','controles internos','compliance','governança']: scores['CICS'] += text.lower().count(w)*2
    for w in ['auditoria','auditoria interna','baseada em riscos']: scores['ABR'] += text.lower().count(w)*2
    for w in ['gestão de riscos','gerenciamento de riscos','riscos corporativos','risk management']: scores['ERM'] += text.lower().count(w)*2
    best=max(scores,key=scores.get)
    why={'CICS':'Os sinais encontrados têm maior relação com fortalecimento de Controles Internos, governança e compliance.', 'ABR':'Os sinais encontrados têm maior relação com Auditoria Interna e uma atuação orientada a riscos.', 'ERM':'Os sinais encontrados têm maior relação com gestão e estruturação de riscos corporativos.'}[best]
    return best,why,scores

def build_messages(company, signal, solution, person=None):
    first=person['name'].split()[0] if person else ''
    hello=f'Olá, {first}. Tudo bem?' if first else 'Olá, tudo bem?'
    sig=signal or 'movimentos públicos recentes relacionados à estrutura de governança, riscos e controles'
    a=f"{hello}\n\nAcompanhamos alguns movimentos recentes da {company} e um ponto nos chamou atenção: {sig.lower()}.\n\nNa Crossover, preparamos uma leitura breve sobre como esse movimento pode conversar com o desenvolvimento da área. Não quero te mandar uma apresentação comercial sem contexto. Posso compartilhar essa análise com você?"
    b=f"{hello}\n\nTemos acompanhado como as áreas de Auditoria, Riscos e Controles estão ampliando seu papel na tomada de decisão. Ao analisar movimentos públicos recentes da {company}, encontramos pontos que podem tornar essa discussão especialmente relevante para a equipe.\n\nPreparamos um resumo objetivo, com foco em {solution}. Posso te enviar?"
    return a,b

@app.route('/api/analyze',methods=['POST'])
def analyze():
    key=os.getenv('TAVILY_API_KEY')
    if not key: return jsonify({'error':'TAVILY_API_KEY não configurada no servidor.'}),503
    data=request.get_json(silent=True) or {}; company=(data.get('company') or '').strip(); site=(data.get('site') or '').strip()
    if not company: return jsonify({'error':'Informe o nome da empresa.'}),400
    base=f'"{company}"' + (f' {site}' if site else '')
    queries=[
      f'{base} auditoria interna riscos controles internos compliance governança 2026 2027',
      f'{base} vagas auditoria riscos controles internos compliance governança 2026',
      f'{base} nova liderança diretor head auditoria riscos compliance controles 2026',
      f'{base} expansão aquisição reestruturação governança riscos relatório anual 2026',
      f'site:linkedin.com/in "{company}" ("auditoria interna" OR auditoria OR audit OR riscos OR risk OR "controles internos" OR compliance OR governança)',
    f'site:linkedin.com/in "{company}" (head OR diretor OR director OR gerente OR manager OR superintendente) (auditoria OR riscos OR compliance OR controles)',
    f'site:linkedin.com/in "{company}" ("recursos humanos" OR "treinamento e desenvolvimento" OR "learning and development" OR "people" OR "corporate university")',
    ]
    packs=[]
    for q in queries:
        try: packs.append(tavily(q,key,6))
        except Exception as e: packs.append({'results':[],'answer':'','warning':str(e)})
    results=dedupe([r for p in packs for r in p.get('results',[])])
    text=' '.join((r.get('title','')+' '+r.get('content','')) for r in results)
    evidence=[]; raw_score=0
    for code,label,weight,terms in SIGNALS:
        matches=[]
        for r in results:
            t=(r.get('title','')+' '+r.get('content','')).lower()
            if any(term in t for term in terms): matches.append(r)
        if matches:
            raw_score += weight
            best=matches[0]
            evidence.append({'code':code,'label':label,'weight':weight,'summary':best.get('content','')[:260].strip(),'url':best.get('url'),'source':domain(best.get('url','')),'title':best.get('title','')})
    score=min(10, round((raw_score/17)*10,1))
    classification='ALTA OPORTUNIDADE' if score>=7 else 'OPORTUNIDADE MODERADA' if score>=4 else 'BAIXA OPORTUNIDADE'
    action='ABORDAR AGORA' if score>=7 else 'PESQUISAR E ACOMPANHAR' if score>=4 else 'MANTER NO RADAR'
    people=find_people(results,company)
    solution,why,solscores=solution_from_text(text)
    main_signal=evidence[0]['label'] if evidence else ''
    msgA,msgB=build_messages(company,main_signal,solution,people[0] if people else None)
    sources=[{'title':r.get('title',''),'url':r.get('url',''),'source':domain(r.get('url','')),'content':r.get('content','')[:220]} for r in results[:12]]
    return jsonify({'company':company,'score':score,'classification':classification,'action':action,'signals':evidence,'people':people,'solution':solution,'solutionWhy':why,'solutionScores':solscores,'messageA':msgA,'messageB':msgB,'sources':sources,'researchNote':'Análise automatizada baseada em resultados públicos retornados pelo Tavily. Confirme cargo e vínculo do decisor na fonte antes do contato.'})
