import 'package:flutter/material.dart';
import '../../../core/theme/app_theme.dart';

class MatchIconTooltip extends StatefulWidget {
  const MatchIconTooltip({
    super.key,
    required this.child,
    required this.title,
    required this.description,
    this.cost,
    this.cooldown,
  });
  final Widget child;
  final String title;
  final String description;
  final int?   cost;
  final int?   cooldown;

  @override
  State<MatchIconTooltip> createState() => _MatchIconTooltipState();
}

class _MatchIconTooltipState extends State<MatchIconTooltip> {
  OverlayEntry? _entry;

  void _show() {
    final box = context.findRenderObject() as RenderBox?;
    if (box == null || !box.hasSize) return;
    final target      = box.localToGlobal(Offset.zero) & box.size;
    final screenWidth = MediaQuery.of(context).size.width;

    const cardMaxWidth = 260.0;
    final cardX       = (target.center.dx - cardMaxWidth / 2).clamp(8.0, screenWidth - cardMaxWidth - 8);
    final arrowOffset = (target.center.dx - cardX).clamp(10.0, cardMaxWidth - 10);

    _entry = OverlayEntry(
      builder: (_) => _TooltipPositioned(
        targetRect:  target,
        title:       widget.title,
        description: widget.description,
        arrowOffset: arrowOffset,
        cost:        widget.cost,
        cooldown:    widget.cooldown,
      ),
    );
    Overlay.of(context).insert(_entry!);
  }

  void _hide() {
    _entry?.remove();
    _entry = null;
  }

  void _showModal() {
    showDialog<void>(
      context: context,
      barrierColor: Colors.black.withValues(alpha: 0.55),
      builder: (ctx) {
        final maxH = MediaQuery.of(ctx).size.height * 0.72;
        return Dialog(
          backgroundColor: const Color(0xFF1A1A2E),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
            side: BorderSide(color: kPrimary.withValues(alpha: 0.45)),
          ),
          child: ConstrainedBox(
            constraints: BoxConstraints(maxHeight: maxH),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                // Cabecera fija: título + coste/cooldown
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 16, 16, 0),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        widget.title,
                        style: const TextStyle(color: Color(0xFFC89B3C), fontSize: 13, fontWeight: FontWeight.bold, letterSpacing: 0.3),
                      ),
                      if ((widget.cost != null && widget.cost! > 0) || (widget.cooldown != null && widget.cooldown! > 0)) ...[
                        const SizedBox(height: 6),
                        Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            if (widget.cost != null && widget.cost! > 0) ...[
                              const Text('🪙', style: TextStyle(fontSize: 11)),
                              const SizedBox(width: 3),
                              Text('${widget.cost}', style: const TextStyle(color: Color(0xFFD4C274), fontSize: 12, fontWeight: FontWeight.w600)),
                            ],
                            if (widget.cost != null && widget.cost! > 0 && widget.cooldown != null && widget.cooldown! > 0)
                              const SizedBox(width: 10),
                            if (widget.cooldown != null && widget.cooldown! > 0) ...[
                              const Text('⏱', style: TextStyle(fontSize: 11)),
                              const SizedBox(width: 3),
                              Text('${widget.cooldown}s', style: TextStyle(color: kForeground.withValues(alpha: 0.75), fontSize: 12, fontWeight: FontWeight.w600)),
                            ],
                          ],
                        ),
                      ],
                    ],
                  ),
                ),
                // Descripción scrollable si es larga
                if (widget.description.isNotEmpty)
                  Flexible(
                    child: SingleChildScrollView(
                      padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
                      child: Text(
                        widget.description,
                        style: TextStyle(color: kForeground.withValues(alpha: 0.65), fontSize: 12, height: 1.5),
                      ),
                    ),
                  ),
                // Botón Close siempre visible
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
                  child: Align(
                    alignment: Alignment.centerRight,
                    child: TextButton(
                      onPressed: () => Navigator.of(ctx).pop(),
                      style: TextButton.styleFrom(
                        foregroundColor: kMuted,
                        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
                        side: BorderSide(color: kMuted.withValues(alpha: 0.3)),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(6)),
                      ),
                      child: const Text('Close', style: TextStyle(fontSize: 12)),
                    ),
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  @override
  void dispose() {
    _hide();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final narrow = MediaQuery.of(context).size.width < 600;
    if (narrow) {
      return GestureDetector(
        onTap: _showModal,
        child: widget.child,
      );
    }
    return MouseRegion(
      onEnter: (_) => _show(),
      onExit:  (_) => _hide(),
      child: widget.child,
    );
  }
}

// ── Internals ─────────────────────────────────────────────────────────────────

class _TooltipPositioned extends StatefulWidget {
  const _TooltipPositioned({
    required this.targetRect,
    required this.title,
    required this.description,
    required this.arrowOffset,
    this.cost,
    this.cooldown,
  });
  final Rect   targetRect;
  final String title;
  final String description;
  final double arrowOffset;
  final int?   cost;
  final int?   cooldown;

  @override
  State<_TooltipPositioned> createState() => _TooltipPositionedState();
}

class _TooltipPositionedState extends State<_TooltipPositioned> {
  bool _showAbove = true;

  void _onPositioned(bool fitsAbove) {
    if (_showAbove != fitsAbove && mounted) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted && _showAbove != fitsAbove) {
          setState(() => _showAbove = fitsAbove);
        }
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return IgnorePointer(
      child: CustomSingleChildLayout(
        delegate: _TooltipDelegate(widget.targetRect, onPositioned: _onPositioned),
        child: Material(
          color: Colors.transparent,
          child: _TooltipCard(
            title:       widget.title,
            description: widget.description,
            arrowOffset: widget.arrowOffset,
            showAbove:   _showAbove,
            cost:        widget.cost,
            cooldown:    widget.cooldown,
          ),
        ),
      ),
    );
  }
}

class _TooltipDelegate extends SingleChildLayoutDelegate {
  const _TooltipDelegate(this.target, {required this.onPositioned});
  final Rect target;
  final void Function(bool) onPositioned;

  @override
  BoxConstraints getConstraintsForChild(BoxConstraints constraints) =>
      const BoxConstraints(maxWidth: 260);

  @override
  Offset getPositionForChild(Size size, Size childSize) {
    final fitsAbove = target.top - childSize.height - 4 >= 8;
    onPositioned(fitsAbove);
    double x = target.center.dx - childSize.width / 2;
    double y = fitsAbove
        ? target.top - childSize.height - 4
        : target.bottom + 4;
    x = x.clamp(8.0, size.width  - childSize.width  - 8);
    y = y.clamp(8.0, size.height - childSize.height - 8);
    return Offset(x, y);
  }

  @override
  bool shouldRelayout(_TooltipDelegate old) => old.target != target;
}

class _TooltipCard extends StatelessWidget {
  const _TooltipCard({
    required this.title,
    required this.description,
    required this.arrowOffset,
    required this.showAbove,
    this.cost,
    this.cooldown,
  });
  final String title;
  final String description;
  final double arrowOffset;
  final bool   showAbove;
  final int?   cost;
  final int?   cooldown;

  @override
  Widget build(BuildContext context) {
    final arrow = LayoutBuilder(
      builder: (_, constraints) => CustomPaint(
        size: Size(constraints.maxWidth, 6),
        painter: _ArrowPainter(
          arrowOffset.clamp(10.0, constraints.maxWidth - 10),
          pointDown: showAbove,
        ),
      ),
    );

    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (!showAbove) arrow,
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
          decoration: BoxDecoration(
            color: const Color(0xFF1A1A2E),
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: kPrimary.withValues(alpha: 0.45)),
            boxShadow: [
              BoxShadow(color: kPrimary.withValues(alpha: 0.12), blurRadius: 12, spreadRadius: 1),
              BoxShadow(color: Colors.black.withValues(alpha: 0.5), blurRadius: 8, offset: const Offset(0, 4)),
            ],
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                style: const TextStyle(color: Color(0xFFC89B3C), fontSize: 12, fontWeight: FontWeight.bold, letterSpacing: 0.3),
              ),
              if (cost != null && cost! > 0 || cooldown != null && cooldown! > 0) ...[
                const SizedBox(height: 4),
                Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    if (cost != null && cost! > 0) ...[
                      const Text('🪙', style: TextStyle(fontSize: 10)),
                      const SizedBox(width: 3),
                      Text('$cost', style: const TextStyle(color: Color(0xFFD4C274), fontSize: 11, fontWeight: FontWeight.w600)),
                    ],
                    if (cost != null && cost! > 0 && cooldown != null && cooldown! > 0)
                      const SizedBox(width: 10),
                    if (cooldown != null && cooldown! > 0) ...[
                      const Text('⏱', style: TextStyle(fontSize: 10)),
                      const SizedBox(width: 3),
                      Text('${cooldown}s', style: TextStyle(color: kForeground.withValues(alpha: 0.75), fontSize: 11, fontWeight: FontWeight.w600)),
                    ],
                  ],
                ),
              ],
              if (description.isNotEmpty) ...[
                const SizedBox(height: 6),
                Text(description, style: TextStyle(color: kForeground.withValues(alpha: 0.65), fontSize: 11, height: 1.5)),
              ],
            ],
          ),
        ),
        if (showAbove) arrow,
      ],
    );
  }
}

class _ArrowPainter extends CustomPainter {
  const _ArrowPainter(this.center, {this.pointDown = true});
  final double center;
  final bool   pointDown;
  static const double _half = 6.0;

  @override
  void paint(Canvas canvas, Size size) {
    final path = pointDown
        ? (Path()
            ..moveTo(center - _half, 0)
            ..lineTo(center + _half, 0)
            ..lineTo(center, size.height)
            ..close())
        : (Path()
            ..moveTo(center - _half, size.height)
            ..lineTo(center + _half, size.height)
            ..lineTo(center, 0)
            ..close());
    canvas.drawPath(path, Paint()..color = const Color(0xFF1A1A2E));

    final border = pointDown
        ? (Path()
            ..moveTo(center - _half, 0)
            ..lineTo(center, size.height)
            ..lineTo(center + _half, 0))
        : (Path()
            ..moveTo(center - _half, size.height)
            ..lineTo(center, 0)
            ..lineTo(center + _half, size.height));
    canvas.drawPath(
      border,
      Paint()
        ..color = kPrimary.withValues(alpha: 0.45)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1,
    );
  }

  @override
  bool shouldRepaint(_ArrowPainter old) => old.center != center || old.pointDown != pointDown;
}
