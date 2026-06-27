package com.example.simpleandroid2;

import android.app.Activity;
import android.os.Bundle;
import android.view.View;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

public class MainActivity extends Activity {
    private boolean screenAlwaysOn = false;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setPadding(16, 16, 16, 16);

        TextView text = new TextView(this);
        text.setText("Simple Android App");
        text.setTextSize(24);
        layout.addView(text);

        final Button button = new Button(this);
        button.setText("Toggle Screen On");
        button.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                if (screenAlwaysOn) {
                    getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
                    screenAlwaysOn = false;
                    button.setText("Toggle Screen On");
                } else {
                    getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
                    screenAlwaysOn = true;
                    button.setText("Toggle Screen Off");
                }
            }
        });
        layout.addView(button);

        setContentView(layout);
    }
}
