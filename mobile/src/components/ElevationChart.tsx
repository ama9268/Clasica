import { View, Text, StyleSheet } from 'react-native';
import Svg, { Path, Polyline, Line, Text as SvgText } from 'react-native-svg';

interface Props {
  data: { dist: number; alt: number }[];
  height?: number;
}

const W = 300;
const PAD_X = 28;
const PAD_Y = 10;

export function ElevationChart({ data, height = 90 }: Props) {
  if (!data || data.length < 2) return null;

  const H = height - 20; // reservar espacio para etiquetas
  const minAlt = Math.min(...data.map((d) => d.alt));
  const maxAlt = Math.max(...data.map((d) => d.alt));
  const maxDist = data[data.length - 1].dist;
  const altRange = maxAlt - minAlt || 1;
  const chartW = W - PAD_X;
  const chartH = H - PAD_Y * 2;

  function toX(dist: number) {
    return PAD_X + (dist / maxDist) * chartW;
  }
  function toY(alt: number) {
    return PAD_Y + ((maxAlt - alt) / altRange) * chartH;
  }

  const pts = data.map((d) => `${toX(d.dist)},${toY(d.alt)}`).join(' ');
  // área de relleno: cerrar el polígono por abajo
  const fillPts =
    `${toX(data[0].dist)},${PAD_Y + chartH} ` +
    pts +
    ` ${toX(data[data.length - 1].dist)},${PAD_Y + chartH}`;

  return (
    <View style={s.container}>
      <Text style={s.label}>PERFIL DE ELEVACIÓN</Text>
      <Svg width="100%" height={height} viewBox={`0 0 ${W} ${H}`}>
        {/* relleno */}
        <Path
          d={`M ${toX(data[0].dist)} ${PAD_Y + chartH} ` +
            data.map((d) => `L ${toX(d.dist)} ${toY(d.alt)}`).join(' ') +
            ` L ${toX(data[data.length - 1].dist)} ${PAD_Y + chartH} Z`}
          fill="rgba(139,26,26,0.15)"
        />
        {/* línea */}
        <Polyline points={pts} fill="none" stroke="#8b1a1a" strokeWidth="1.5" strokeLinejoin="round" />
        {/* línea base */}
        <Line x1={PAD_X} y1={PAD_Y + chartH} x2={W} y2={PAD_Y + chartH} stroke="#d1d5db" strokeWidth="1" />
        {/* etiqueta altitud max */}
        <SvgText x={PAD_X - 2} y={PAD_Y + 4} fontSize="8" fill="#6b7280" textAnchor="end">
          {Math.round(maxAlt)}
        </SvgText>
        {/* etiqueta altitud min */}
        <SvgText x={PAD_X - 2} y={PAD_Y + chartH} fontSize="8" fill="#6b7280" textAnchor="end">
          {Math.round(minAlt)}
        </SvgText>
        {/* etiqueta distancia total */}
        <SvgText x={W} y={PAD_Y + chartH + 8} fontSize="8" fill="#6b7280" textAnchor="end">
          {maxDist.toFixed(1)} km
        </SvgText>
      </Svg>
    </View>
  );
}

const s = StyleSheet.create({
  container: { backgroundColor: '#fff', marginHorizontal: 0, paddingHorizontal: 16, paddingTop: 12, paddingBottom: 4 },
  label: { fontSize: 10, fontWeight: '700', color: '#6b7280', letterSpacing: 2, marginBottom: 6 },
});
