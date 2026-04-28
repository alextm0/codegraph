const fs = require('fs')

let content = fs.readFileSync('src/components/graph/GraphCanvas.tsx', 'utf-8')

const s1 = `  const scaleRef = useRef(1)

  /* ResizeObserver */`
const r1 = `  const scaleRef = useRef(1)

  const [hiddenNodeTypes, setHiddenNodeTypes] = useState<Set<string>>(new Set())
  const [hiddenEdgeTypes, setHiddenEdgeTypes] = useState<Set<string>>(new Set())

  const filteredNodes = nodes.filter(n => !hiddenNodeTypes.has(n.label.toLowerCase()))
  const filteredEdges = edges.filter(e => {
    let typeKey = e.type.toLowerCase()
    if (typeKey === 'inherits_from') typeKey = 'inherits'
    return !hiddenEdgeTypes.has(typeKey)
  })

  /* ResizeObserver */`
content = content.replace(s1, r1)

content = content.replace('if (!nodes.length) {', 'if (!filteredNodes.length) {')
content = content.replace('nodes.forEach(n => { nodeById[n.id] = n })', 'filteredNodes.forEach(n => { nodeById[n.id] = n })')
content = content.replace('const links: D3Edge[] = edges', 'const links: D3Edge[] = filteredEdges')
content = content.replace('.data(nodes.filter(d => d.is_seed))', '.data(filteredNodes.filter(d => d.is_seed))')
content = content.replace('.data(nodes)', '.data(filteredNodes)')
content = content.replace('const sim = d3.forceSimulation<D3Node, D3Edge>(nodes)', 'const sim = d3.forceSimulation<D3Node, D3Edge>(filteredNodes)')
content = content.replace('}, [nodes, edges, onNodeSelect])', '}, [filteredNodes, filteredEdges, onNodeSelect])')

content = content.replace('edges.forEach(e => {', 'filteredEdges.forEach(e => {')
content = content.replace('const sn = nodes.find(n => n.id === selectedNode.id)', 'const sn = filteredNodes.find(n => n.id === selectedNode.id)')
content = content.replace('}, [selectedNode, nodes, edges])', '}, [selectedNode, filteredNodes, filteredEdges])')

content = content.replace('nodeCount={nodes.length}', 'nodeCount={filteredNodes.length}')
content = content.replace('edgeCount={edges.length}', 'edgeCount={filteredEdges.length}')
content = content.replace('seedCount={nodes.filter(n => n.is_seed).length}', 'seedCount={filteredNodes.filter(n => n.is_seed).length}')

const s2 = `<LatticeLegend />`
const r2 = `<LatticeLegend 
            hiddenNodeTypes={hiddenNodeTypes} 
            setHiddenNodeTypes={setHiddenNodeTypes}
            hiddenEdgeTypes={hiddenEdgeTypes}
            setHiddenEdgeTypes={setHiddenEdgeTypes}
          />`
content = content.replace(s2, r2)

const s3 = `function LatticeLegend() {`
const r3 = `function LatticeLegend({
  hiddenNodeTypes, setHiddenNodeTypes,
  hiddenEdgeTypes, setHiddenEdgeTypes
}: {
  hiddenNodeTypes: Set<string>
  setHiddenNodeTypes: React.Dispatch<React.SetStateAction<Set<string>>>
  hiddenEdgeTypes: Set<string>
  setHiddenEdgeTypes: React.Dispatch<React.SetStateAction<Set<string>>>
}) {`
content = content.replace(s3, r3)

const s4 = `        {nodeTypes.map(([label, color]) => (
          <div
            key={label}
            style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}
          >
            <div style={{ width: 7, height: 7, borderRadius: '50%', background: color }} />
            <div style={{ color: 'var(--text-dim)' }}>{label}</div>
          </div>
        ))}`
const r4 = `        {nodeTypes.map(([label, color]) => {
          const isHidden = hiddenNodeTypes.has(label)
          return (
            <div
              key={label}
              style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2, cursor: 'pointer', opacity: isHidden ? 0.4 : 1 }}
              onClick={() => {
                setHiddenNodeTypes(prev => {
                  const next = new Set(prev)
                  if (next.has(label)) next.delete(label)
                  else next.add(label)
                  return next
                })
              }}
            >
              <div style={{ width: 7, height: 7, borderRadius: '50%', background: color }} />
              <div style={{ color: 'var(--text-dim)' }}>{label}</div>
            </div>
          )
        })}`
content = content.replace(s4, r4)

const s5 = `        {edgeTypes.map(([label, color]) => (
          <div
            key={label}
            style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}
          >
            <div style={{ width: 16, height: 1.5, background: color }} />
            <div style={{ color: 'var(--text-dim)' }}>{label}</div>
          </div>
        ))}`
const r5 = `        {edgeTypes.map(([label, color]) => {
          const isHidden = hiddenEdgeTypes.has(label.toLowerCase())
          return (
            <div
              key={label}
              style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2, cursor: 'pointer', opacity: isHidden ? 0.4 : 1 }}
              onClick={() => {
                setHiddenEdgeTypes(prev => {
                  const next = new Set(prev)
                  const key = label.toLowerCase()
                  if (next.has(key)) next.delete(key)
                  else next.add(key)
                  return next
                })
              }}
            >
              <div style={{ width: 16, height: 1.5, background: color }} />
              <div style={{ color: 'var(--text-dim)' }}>{label}</div>
            </div>
          )
        })}`
content = content.replace(s5, r5)

fs.writeFileSync('src/components/graph/GraphCanvas.tsx', content, 'utf-8')
console.log('Done!')
