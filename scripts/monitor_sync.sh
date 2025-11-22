#!/bin/bash
# Monitor sync progress in real-time

echo "======================================================================"
echo "📊 Monitoring Sync Progress"
echo "======================================================================"
echo ""

while true; do
    # Get current count
    COUNT=$(curl -s http://localhost:7333/collections/legal_documents | \
            python3 -c "import sys, json; print(json.load(sys.stdin)['result']['points_count'])" 2>/dev/null)
    
    # Get status
    STATUS=$(curl -s http://localhost:7333/collections/legal_documents | \
             python3 -c "import sys, json; print(json.load(sys.stdin)['result']['status'])" 2>/dev/null)
    
    # Calculate progress
    EXPECTED=4304
    if [ ! -z "$COUNT" ]; then
        PROGRESS=$(echo "scale=1; $COUNT * 100 / $EXPECTED" | bc 2>/dev/null)
        
        # Clear line and print
        echo -ne "\r\033[K"
        echo -ne "Points: $COUNT / $EXPECTED ($PROGRESS%) | Status: $STATUS"
        
        # Check if complete
        if [ "$COUNT" -ge "$EXPECTED" ]; then
            echo ""
            echo ""
            echo "======================================================================"
            echo "✅ Sync Complete!"
            echo "======================================================================"
            echo "Final count: $COUNT"
            echo "Expected: $EXPECTED"
            echo "Status: $STATUS"
            echo ""
            
            # Show last few log entries
            echo "Recent sync logs:"
            docker-compose -f deployment/docker/docker-compose.yml logs --tail=5 core-api 2>/dev/null | \
                grep -i "synced\|auto-detected" || echo "No recent logs"
            
            break
        fi
    fi
    
    sleep 2
done

echo ""
echo "Run this to verify:"
echo "  docker exec core-api python scripts/detailed_sync_report.py"
echo ""
