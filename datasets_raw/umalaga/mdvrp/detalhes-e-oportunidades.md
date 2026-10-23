detalhes e oportunidades:

- métrica utilizada: a distância atual é euclidiana. Sendo a métrica euclidiana, isso é um float. Transformo isso em inteiros, mas só falo disso quando realmente estou implementando, fica meio solto. Contradições. Colocar logo no início o arredondamento do inteiro mais próximo. Colocar o esclarecimento logo no início, demonstrando que a tsplib também arredonda.
- Passada do 2-opt hora é 40, hora é 50, mas tenho que deixar claro para quais instâncias há mudanças de parâmetros.
- Questão na distorçào de comportamento para o caso de grandes instâncias.
- métodos estatísticos: Testes são feitos como hipóteses. 2 coisas são faltantes:
  + Caracterização dos testes de hipótese: só apresento em termos textuais. Não há informação sobre os resultados. Testes devem ser colocados em anexo.
  + citaçào de demŝar: os testes em si não estão registrados. Como é o procedimento para tal? Qual a formulação? Qual a hipótese nula e hipótese alternativa? Qual a estatística que será usada?
    * Resultados dos testes para observar o que estou fazendo não constam, precisam estar em apêndices. Devem ser referenciados dentro do texto.
    * Estender a tabela 4 e os problemas analisados e seus resultados em um apêndice.
    * Resultados da análise não estão presentes, apenas os dados brutos: vê-se a descrição, tamanho, alternativas de implementação, gap médio (sem citar a qual a melhor solução efetiva). Tempo computacional tem muitas variâncias, de segundos para minutos. Tempos explodem para instâncias maiores.
    * Apresentar resumo dos testes de hipótese em 4.2. Testes de hipótese têm sempre uma estatística contendo o resultado dos testes. Como cheguei àquele resultado?
    * Como as conclusões se relacionam com os métodos estatísticos?
    * Adicionar ao capítulo 4 também, nos resultados, um exemplo de como os testes estatísticos
- Como ficam os testes para problemas maiores para o qual a implementação. CPU só vai até 100 cidades.
- 2-opt começa a fazer sentido após o algoritmo genético após o algoritmo genético já ter feito parte.
- GLS elege uma região onde o 2-opt será realizado. Não faz todo o 2-opt e escolhe o melhor, nem faz a passad completa. Ele marca onde houve modificações e aplica o 2-opt ao entorno. Suponha 1000 cidades.
  + 2-opt é feito uma vez no início, e após, apenas onde há mudança. Ao invés de $1000^2$, pode-se reduzir para $100^2$, por exemplo, ou menos.
  + é o conceito de Local Search.
  + Utilizar first-improvement ao invés de best-improvement, pode melhorar o desempenho.
- Definição dos objetivos e conclusões.
- Minha questão é muito menos testar o TSP, mas na implementaçào e comparação testando estratégias em GPU. Ênfase das conclusões em desempenho, alocações e comparação.
- Tirar a "descrição" nas referências. Deixar apenas a referência.
- Fazer uma boa leitura em relação aos objetivos. O foco é alocação em GPUs e comportamento. TSP talvez não seja o foco principal: o TSP age como o benchmark.
- Não deixar dados vazios na apresentação.
- Estabelecer limite para tempo de processamento.
  + limitar em 5m o processamento.
  + Não faz mais sentido comparar o tempo computacional.
