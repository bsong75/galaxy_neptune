import { useCallback, useEffect, useRef } from 'react';

export default function ResizeHandle({ onResize, side }) {
  const dragging = useRef(false);
  const startX = useRef(0);
  const startWidth = useRef(0);

  const handleMouseDown = useCallback((e) => {
    e.preventDefault();
    dragging.current = true;
    startX.current = e.clientX;
    startWidth.current = 0;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  }, []);

  useEffect(() => {
    const handleMouseMove = (e) => {
      if (!dragging.current) return;
      const delta = e.clientX - startX.current;
      onResize(side === 'left' ? delta : -delta);
      startX.current = e.clientX;
    };

    const handleMouseUp = () => {
      dragging.current = false;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [onResize, side]);

  return (
    <div
      onMouseDown={handleMouseDown}
      style={{
        width: '5px',
        cursor: 'col-resize',
        background: 'transparent',
        flexShrink: 0,
        zIndex: 5,
      }}
      onMouseEnter={(e) => { e.target.style.background = 'var(--border-hover)'; }}
      onMouseLeave={(e) => { if (!dragging.current) e.target.style.background = 'transparent'; }}
    />
  );
}
