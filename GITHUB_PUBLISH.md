# Publicar Bal no GitHub - Checklist

## Pré-requisitos ✗/✅

- [ ] **README.md** - Documentação principal
- [ ] **LICENSE** - Licença MIT (já existe)
- [ ] **.gitignore** - Arquivos a ignorar
- [ ] **tests/run_examples.py** - Testes passando
- [ ] **gh autenticado** - Necessário para criar repo

## Estado Atual ✅

### Arquivos Presentes
- `README.md` - ✅ Existe
- `LICENSE` - ✅ Criado (MIT)
- `.gitignore` - ✅ Existe
- `tests/run_examples.py` - ✅ Existe
- `src/compiler.py` - ✅ Self-hosting (lexer + parser em bal)

### Testes ✅
```
20/20 match ✓
```

### Dependências
- Py >= 3.8 (já verificado)
- Nenhuma dependência externa

## Passos para Publicar

```bash
# 1. Verificar tests
cd /home/richard/Projetos/bal
python3 tests/run_examples.py

# 2. Autenticar gh (se não estiver)
gh auth login

# 3. Criar e publicar
gh repo create bal --public --source=. --push
```

## Pós-publicação
- [ ] Atualizar README com link do GitHub
- [ ] Verificar Actions/CI no GitHub
- [ ] Criar release v1.0.0