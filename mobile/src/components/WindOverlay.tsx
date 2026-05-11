import React, { useEffect, useMemo, useRef } from 'react';
import { View, StyleSheet, Dimensions } from 'react-native';
import Svg, { Line, Defs, LinearGradient, Stop } from 'react-native-svg';
import Animated, { 
  useSharedValue, 
  useAnimatedProps, 
  withRepeat, 
  withTiming, 
  easing,
  interpolate,
  useAnimatedStyle,
  withDelay
} from 'react-native-reanimated';

const { width: SCREEN_WIDTH } = Dimensions.get('window');

const degMap: Record<string, number> = {
  'N': 0, 'NNE': 22.5, 'NE': 45, 'ENE': 67.5, 'E': 90, 'ESE': 112.5, 'SE': 135, 'SSE': 157.5,
  'S': 180, 'SSO': 202.5, 'SO': 225, 'OSO': 247.5, 'O': 270, 'ONO': 292.5, 'NO': 315, 'NNO': 337.5, 'C': 0
};

interface WindOverlayProps {
  direction: string;
  speed: number;
  height: number;
}

const PARTICLE_COUNT = 40; // Fewer particles than web for performance

const AnimatedLine = Animated.createAnimatedComponent(Line);

const WindParticle = ({ angle, speed, containerWidth, containerHeight }: any) => {
  const progress = useSharedValue(0);
  const startX = useMemo(() => Math.random() * containerWidth, []);
  const startY = useMemo(() => Math.random() * containerHeight, []);
  const length = useMemo(() => Math.random() * 30 + 20, []);
  const duration = useMemo(() => (3000 / (speed / 10 + 0.5)) * (0.8 + Math.random() * 0.4), [speed]);
  const delay = useMemo(() => Math.random() * 2000, []);

  const dx = Math.sin(angle);
  const dy = -Math.cos(angle);

  useEffect(() => {
    progress.value = withDelay(
      delay,
      withRepeat(
        withTiming(1, { duration, easing: easing.linear }),
        -1,
        false
      )
    );
  }, []);

  const animatedProps = useAnimatedProps(() => {
    const currentX = (startX + dx * progress.value * 200) % (containerWidth + 100);
    const currentY = (startY + dy * progress.value * 200) % (containerHeight + 100);
    
    // Normalize to wrap around correctly
    const x = currentX < -50 ? currentWidth + currentX : currentX > containerWidth + 50 ? currentX - containerWidth - 100 : currentX;
    const y = currentY < -50 ? currentHeight + currentY : currentY > containerHeight + 50 ? currentY - containerHeight - 100 : currentY;

    return {
      x1: x,
      y1: y,
      x2: x - dx * length,
      y2: y - dy * length,
      strokeOpacity: interpolate(progress.value, [0, 0.2, 0.8, 1], [0, 0.6, 0.6, 0]),
    };
  });

  return (
    <AnimatedLine
      animatedProps={animatedProps}
      stroke="url(#windGrad)"
      strokeWidth="2"
      strokeLinecap="round"
    />
  );
};

export const WindOverlay = ({ direction, speed, height }: WindOverlayProps) => {
  const angle = ((degMap[direction] || 0) + 180) * (Math.PI / 180);
  const containerWidth = SCREEN_WIDTH;

  return (
    <View style={[styles.container, { height }]} pointerEvents="none">
      <Svg width="100%" height="100%">
        <Defs>
          <LinearGradient id="windGrad" x1="0%" y1="0%" x2="100%" y2="0%">
            <Stop offset="0%" stopColor="#00a0ff" stopOpacity="0.8" />
            <Stop offset="100%" stopColor="#00a0ff" stopOpacity="0" />
          </LinearGradient>
        </Defs>
        {Array.from({ length: PARTICLE_COUNT }).map((_, i) => (
          <WindParticle 
            key={i} 
            angle={angle} 
            speed={speed} 
            containerWidth={containerWidth} 
            containerHeight={height} 
          />
        ))}
      </Svg>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    zIndex: 10,
  },
});
