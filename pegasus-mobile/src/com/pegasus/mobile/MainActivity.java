package com.pegasus.mobile;

import android.app.Activity;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.os.BatteryManager;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.os.StatFs;
import android.view.ViewGroup;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import java.util.List;

public class MainActivity extends Activity {
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        ScrollView scroll = new ScrollView(this);
        LinearLayout container = new LinearLayout(this);
        container.setOrientation(LinearLayout.VERTICAL);
        container.setPadding(24, 24, 24, 24);

        addHeader(container, "Pegasus Mobile v1.4", "Native Android companion (APK)");
        addItem(container, "Device Model", Build.MODEL);
        addItem(container, "Manufacturer", Build.MANUFACTURER);
        addItem(container, "Android Version", Build.VERSION.RELEASE + " (SDK " + Build.VERSION.SDK_INT + ")");
        addItem(container, "Build Tags", Build.TAGS);

        int batLevel = getBatteryLevel();
        addItem(container, "Battery Level", batLevel + "%");

        long[] storage = getStorageInfo();
        addItem(container, "Storage Total", formatBytes(storage[0]));
        addItem(container, "Storage Free", formatBytes(storage[1]));

        int pkgCount = getInstalledPackageCount();
        addItem(container, "Installed Packages", String.valueOf(pkgCount));

        scroll.addView(container);
        setContentView(scroll);
    }

    private void addHeader(LinearLayout parent, String title, String subtitle) {
        TextView tv = new TextView(this);
        tv.setText(title + "\n" + subtitle);
        tv.setTextSize(22);
        tv.setPadding(0, 0, 0, 24);
        parent.addView(tv);
    }

    private void addItem(LinearLayout parent, String label, String value) {
        TextView tv = new TextView(this);
        tv.setText(label + ": " + value);
        tv.setTextSize(16);
        tv.setPadding(0, 4, 0, 4);
        parent.addView(tv);
    }

    private int getBatteryLevel() {
        BatteryManager bm = (BatteryManager) getSystemService(BATTERY_SERVICE);
        return bm.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY);
    }

    private long[] getStorageInfo() {
        StatFs st = new StatFs(Environment.getDataDirectory().getAbsolutePath());
        long total = st.getTotalBytes();
        long free = st.getAvailableBytes();
        return new long[]{total, free};
    }

    private int getInstalledPackageCount() {
        PackageManager pm = getPackageManager();
        List<PackageInfo> pkgs = pm.getInstalledPackages(PackageManager.GET_ACTIVITIES);
        return pkgs == null ? 0 : pkgs.size();
    }

    private String formatBytes(long bytes) {
        double kb = bytes / 1024.0;
        double mb = kb / 1024.0;
        return String.format("%.2f MB", mb);
    }
}
