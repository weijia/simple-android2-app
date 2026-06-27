package com.example.simpleandroid2;

import android.app.Activity;
import android.os.Bundle;
import android.view.View;
import android.view.WindowManager;
import android.widget.Button;

public class MainActivity extends Activity {
    private boolean screenAlwaysOn = false;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        final Button toggleButton = (Button) findViewById(R.id.toggleScreenOn);
        toggleButton.setText(R.string.screen_off);

        toggleButton.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                if (screenAlwaysOn) {
                    getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
                    screenAlwaysOn = false;
                    toggleButton.setText(R.string.screen_off);
                } else {
                    getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
                    screenAlwaysOn = true;
                    toggleButton.setText(R.string.screen_on);
                }
            }
        });
    }
}
