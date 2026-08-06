interface ComOrdem {
  id: string;
  ordem: number;
}

export function reordenarPorArrasto<T extends ComOrdem>(
  itens: T[],
  activeId: string,
  overId: string,
): T[] {
  const ordenados = [...itens].sort((a, b) => a.ordem - b.ordem);
  const fromIndex = ordenados.findIndex((item) => item.id === activeId);
  const toIndex = ordenados.findIndex((item) => item.id === overId);

  if (fromIndex === -1 || toIndex === -1 || fromIndex === toIndex) {
    return ordenados;
  }

  const [movido] = ordenados.splice(fromIndex, 1);
  ordenados.splice(toIndex, 0, movido);

  return ordenados.map((item, index) => ({ ...item, ordem: index + 1 }));
}
