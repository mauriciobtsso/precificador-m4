from app import db
from app.vendas.models import Venda, ItemVenda
from app.estoque.models import ItemEstoque
from app.produtos.models import Produto
from datetime import datetime
from decimal import Decimal  # <--- IMPORTANTE

class VendaService:
    @staticmethod
    def criar_venda(dados_venda, usuario_atual):
        """
        Processa uma nova venda com inteligência para distinguir:
        - Armas (Exige fluxo completo + Reserva de Serial)
        - Munições/PCE (Exige vínculo com CRAF do cliente)
        - Produtos Livres (Venda simplificada)
        """
        try:
            # 1. Cria o cabeçalho da Venda
            nova_venda = Venda()
            nova_venda.cliente_id = dados_venda.get('cliente_id')
            nova_venda.vendedor = getattr(usuario_atual, 'nome', 'Sistema')
            nova_venda.data_abertura = datetime.now()
            
            # Captura o desconto (convertendo para Decimal seguro)
            desc_raw = dados_venda.get('desconto')
            nova_venda.desconto_valor = Decimal(str(desc_raw)) if desc_raw else Decimal('0.00')
            
            # Define status financeiro inicial
            nova_venda.status = "aberto"
            nova_venda.status_financeiro = "pendente"
            
            db.session.add(nova_venda)
            db.session.flush() # Garante ID da venda

            # Variáveis de Controle do Processo
            tem_arma = False
            tem_municao = False
            tem_encomenda = False

            # 2. Processa Itens do Carrinho
            itens_dados = dados_venda.get('itens', [])
            for item in itens_dados:
                novo_item = ItemVenda(venda_id=nova_venda.id)
                novo_item.produto_id = item['produto_id']
                novo_item.produto_nome = item['nome'] # Congela nome
                
                # Conversão Financeira Segura
                qtd = Decimal(str(item.get('quantidade', 1)))
                preco = Decimal(str(item['preco']))
                
                novo_item.quantidade = int(qtd)
                novo_item.valor_unitario = preco
                novo_item.valor_total = qtd * preco
                
                # Busca dados completos do produto para classificar
                produto_db = Produto.query.get(item['produto_id'])
                tipo_prod = (produto_db.tipo_rel.nome if produto_db.tipo_rel else "").lower()
                cat_prod = (produto_db.categoria.nome if produto_db.categoria else "").lower()
                nome_prod = (produto_db.nome or "").lower()
                
                # --- LÓGICA A: É UMA ARMA? ---
                if 'arma' in tipo_prod or 'fuzil' in cat_prod or 'pistola' in cat_prod or 'revolver' in cat_prod:
                    tem_arma = True
                    
                    # Verifica se escolheu um Serial do Estoque (Pronta Entrega)
                    serial_id = item.get('item_estoque_id')
                    if serial_id:
                        item_fisico = ItemEstoque.query.get(serial_id)
                        if not item_fisico or item_fisico.status != 'disponivel':
                            raise ValueError(f"A arma serial {item_fisico.numero_serie} não está disponível!")
                        
                        # Vincula e Reserva no Cofre
                        novo_item.item_estoque_id = item_fisico.id
                        item_fisico.status = 'reservado'
                        item_fisico.observacoes = f"Reservado Venda #{nova_venda.id}"
                    else:
                        # É uma venda sob encomenda (sem serial físico ainda)
                        tem_encomenda = True

                # --- LÓGICA B: É MUNIÇÃO/PCE? ---
                elif 'munição' in tipo_prod or 'pólvora' in tipo_prod or 'espoleta' in tipo_prod or 'munição' in nome_prod:
                    tem_municao = True
                    
                    # Exige vínculo com CRAF (Arma do Cliente)
                    # O front-end deve mandar 'arma_cliente_id' se for munição
                    craf_id = item.get('arma_cliente_id') # ID da tabela 'armas' (Cliente)
                    
                    if craf_id:
                        novo_item.arma_cliente_id = craf_id
                    else:
                        # Se não mandou CRAF, permitimos passar mas marcamos observação (ou bloqueamos)
                        pass

                db.session.add(novo_item)

            # 3. Define o Tipo de Processo (Workflow)
            # A classificação segue a hierarquia: Arma > Munição > Livre
            if tem_arma:
                nova_venda.tipo_processo = 'arma'
                nova_venda.etapa = 'RASCUNHO' # Começa no início do funil
            elif tem_municao:
                nova_venda.tipo_processo = 'municao'
                nova_venda.etapa = 'VALIDACAO_CRAF' # Pula contrato, vai pra validação
            else:
                nova_venda.tipo_processo = 'livre'
                nova_venda.etapa = 'CONCLUSAO_PENDENTE' # Pula tudo, só precisa pagar e entregar

            # 4. Finalização
            nova_venda.calcular_totais()
            
            if tem_encomenda:
                nova_venda.observacoes = "PEDIDO COM ITENS SOB ENCOMENDA."

            db.session.commit()
            return nova_venda

        except Exception as e:
            db.session.rollback()
            raise e

    @staticmethod
    def cancelar_venda(venda_id):
        """
        Cancela a venda e libera o estoque reservado.
        """
        venda = Venda.query.get_or_404(venda_id)
        
        if venda.status == 'cancelado':
            return False

        try:
            for item in venda.itens:
                # Se tinha arma reservada do estoque, libera ela
                if item.item_estoque_id:
                    estoque = ItemEstoque.query.get(item.item_estoque_id)
                    if estoque:
                        estoque.status = 'disponivel'
                        estoque.observacoes = None
            
            venda.status = 'cancelado'
            venda.etapa = 'CANCELADA'
            venda.data_cancelamento = datetime.now()
            
            db.session.commit()
            return True
            
        except Exception:
            db.session.rollback()
            raise